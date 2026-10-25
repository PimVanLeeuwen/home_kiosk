from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import anthropic
import httpx
import httpx2
import pytest
from fastapi.testclient import TestClient

from app import ai, main
from app.alerts import core
from app.alerts.telegram import Telegram

CFG = {
    "timezone": "Europe/Amsterdam",
    "ai": {"api_key": "sk-test", "cap_eur": 5},
    "telegram": {"token": "t", "chats": {"nas": {"id": "-1", "label": "NAS"}}},
}
NOW = datetime(2026, 10, 14, 10, 0, tzinfo=UTC)


@pytest.fixture(autouse=True)
def feature(monkeypatch, store):
    """One feature for the tests; the real ones arrive with their steps."""
    monkeypatch.setattr(ai, "FEATURES", {"notes": "Update notes"})
    ai.ensure_tables(store)
    ai.set_switches(store, {"notes": True})


class FakeClaude:
    def __init__(self, text="A short note.", stop="end_turn", tokens=(1000, 200), fail=None):
        self.calls: list[dict] = []
        self.text, self.stop, self.tokens, self.fail = text, stop, tokens, fail

    def __call__(self, api_key):
        self.key = api_key
        return SimpleNamespace(messages=SimpleNamespace(create=self.create))

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        if self.fail:
            raise self.fail
        usage = SimpleNamespace(input_tokens=self.tokens[0], output_tokens=self.tokens[1],
                                cache_read_input_tokens=0, cache_creation_input_tokens=0)
        return SimpleNamespace(stop_reason=self.stop, usage=usage,
                               content=[SimpleNamespace(type="thinking", thinking=""),
                                        SimpleNamespace(type="text", text=self.text)])


class Sent:
    def __init__(self):
        self.texts = []

    def client(self):
        def handler(request):
            self.texts.append(json.loads(request.content)["text"])
            return httpx.Response(200, json={"ok": True, "result": {}})

        return Telegram("t", transport=httpx.MockTransport(handler))


def ask(store, claude, cfg=CFG, now=NOW, prompt="What changed in Sonarr 4.1?", telegram=None):
    return asyncio.run(ai.ask(cfg, store, feature="notes", model=ai.SCHEDULED_MODEL,
                              system="Be brief.", prompt=prompt, now=now, client=claude,
                              telegram=telegram))


def test_asks_haiku_with_the_key_and_low_effort_and_keeps_the_text(store):
    claude = FakeClaude()

    assert ask(store, claude) == "A short note."
    call = claude.calls[0]
    assert claude.key == "sk-test"
    assert call["model"] == "claude-haiku-5-5" and call["system"] == "Be brief."
    assert call["messages"] == [{"role": "user", "content": "What changed in Sonarr 4.1?"}]
    assert call["output_config"] == {"effort": "low"}


def test_the_same_input_is_answered_from_the_cache_without_paying_again(store):
    claude = FakeClaude()
    ask(store, claude)

    assert ask(store, claude) == "A short note."
    assert len(claude.calls) == 1
    ask(store, claude, prompt="What changed in Radarr 6?")
    assert len(claude.calls) == 2


def test_records_each_call_and_its_price(store):
    ask(store, FakeClaude(tokens=(10_000, 2_000)))

    spent, calls = ai.month_spend(store, CFG, NOW)
    # Haiku 5.5: 10K in at $0.10 and 2K out at $0.50 per million.
    assert calls == 1 and spent == pytest.approx(0.002)


def test_a_long_prompt_costs_haiku_its_higher_rate():
    usage = SimpleNamespace(input_tokens=150_000, output_tokens=1_000,
                            cache_read_input_tokens=0, cache_creation_input_tokens=0)

    assert ai.cost_usd("claude-haiku-5-5", usage) == pytest.approx(0.075 + 0.0025)
    assert ai.cost_usd("claude-sonnet-5-5", usage) == pytest.approx(0.30 + 0.01)


def test_nothing_is_asked_when_switched_off_or_without_a_key(store):
    claude = FakeClaude()
    ai.set_switches(store, {"notes": False})
    assert ask(store, claude) is None

    ai.set_switches(store, {"notes": True})
    assert ask(store, claude, cfg=CFG | {"ai": {"api_key": ""}}) is None
    assert claude.calls == []


def test_stops_at_the_cap_until_the_next_month(store):
    big = FakeClaude(tokens=(0, 10_000_000))  # $5 of Haiku output
    ask(store, big)

    claude = FakeClaude()
    assert ask(store, claude, prompt="another") is None
    assert claude.calls == []
    assert ask(store, claude, prompt="another", now=datetime(2026, 11, 1, 9, tzinfo=UTC))
    assert len(claude.calls) == 1


def test_warns_once_a_month_past_eighty_percent(store):
    sent = Sent()
    ask(store, FakeClaude(tokens=(0, 8_200_000)), telegram=sent.client())  # $4.10
    ask(store, FakeClaude(), prompt="again", now=NOW + timedelta(hours=1), telegram=sent.client())

    assert len(sent.texts) == 1
    assert "AI spend at 82% of the monthly cap" in sent.texts[0]
    assert core.get_setting(store, ai.WARNED, "") == "2026-10"


def test_a_refusal_or_a_cut_answer_is_no_answer_and_not_kept(store):
    assert ask(store, FakeClaude(stop="refusal")) is None
    assert ask(store, FakeClaude(stop="max_tokens")) is None
    assert ai.month_spend(store, CFG, NOW)[1] == 2  # both were paid for
    assert ask(store, FakeClaude()) == "A short note."


def test_api_failures_are_no_answer(store):
    request = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")
    assert ask(store, FakeClaude(fail=anthropic.APIConnectionError(request=request))) is None
    over = anthropic.InternalServerError(
        "overloaded", response=httpx2.Response(529, request=request), body=None)
    assert ask(store, FakeClaude(fail=over)) is None
    assert ai.month_spend(store, CFG, NOW) == (0.0, 0)


def test_a_switch_must_name_a_feature(store):
    with pytest.raises(ValueError, match="unknown feature: digest"):
        ai.set_switches(store, {"digest": True})


@pytest.fixture
def client(store):
    main.app.state.store = store
    main.app.state.config = CFG
    return TestClient(main.app)


def test_settings_show_the_spend_and_switch_a_feature(client, store):
    ask(store, FakeClaude(tokens=(10_000, 2_000)), now=datetime.now(UTC))

    body = client.get("/api/ai").json()
    assert body["configured"] is True and body["cap"] == 5 and body["capped"] is False
    assert body["calls"] == 1 and body["spent"] == pytest.approx(0.002)
    assert body["features"] == [{"id": "notes", "label": "Update notes", "on": True}]
    assert "sk-test" not in json.dumps(body)

    off = client.put("/api/ai/features", json={"notes": False},
                     headers={"Origin": "http://testserver"})
    assert off.status_code == 200 and off.json()["features"][0]["on"] is False
    bad = client.put("/api/ai/features", json={"nope": True}, headers={"Origin": "http://testserver"})
    assert bad.status_code == 422
