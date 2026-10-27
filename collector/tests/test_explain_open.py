from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import httpx
import pytest

from app import ai, explain_open
from app.alerts import bot
from app.alerts.telegram import Telegram

CFG = {
    "timezone": "Europe/Amsterdam",
    "ai": {"api_key": "sk-test"},
    "telegram": {"token": "t", "chats": {"nas": {"id": "-1"}, "portfolio": {"id": "-2"}}},
}
NOW = datetime(2026, 10, 29, 5, 30, tzinfo=UTC)
ANSWER = {"alerts": [
    {"n": 2, "cause": "The downloads pool is nearly full.", "todo": "Clear finished downloads."},
    {"n": 1, "cause": "TransIP reports an outage.", "todo": "Nothing; it should pass."},
    {"n": 9, "cause": "Not asked about.", "todo": "Left out."}]}


class FakeClaude:
    """Answers on the beta path (Sonnet's fallback) and records what it was sent."""

    def __init__(self, answer=ANSWER):
        self.answer, self.calls = answer, []

    def __call__(self, api_key):
        create = self.create
        return SimpleNamespace(beta=SimpleNamespace(messages=SimpleNamespace(create=create)),
                               messages=SimpleNamespace(create=create))

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        usage = SimpleNamespace(input_tokens=2000, output_tokens=200,
                                cache_read_input_tokens=0, cache_creation_input_tokens=0)
        text = self.answer if isinstance(self.answer, str) else json.dumps(self.answer)
        return SimpleNamespace(stop_reason="end_turn", usage=usage, model="claude-sonnet-5-5",
                               content=[SimpleNamespace(type="text", text=text)])


class FakeTelegram:
    """Records every Bot API call."""

    def __init__(self):
        self.calls = []

    def client(self):
        def handler(request):
            self.calls.append((request.url.path.rsplit("/", 1)[-1], json.loads(request.content)))
            return httpx.Response(200, json={"ok": True, "result": {"message_id": 99}})

        return Telegram("t", transport=httpx.MockTransport(handler))


def open_incident(store, key, rule, severity, title, body="", hours=2):
    at = (NOW - timedelta(hours=hours)).isoformat()
    with store.connect() as conn:
        conn.execute("INSERT INTO alert_incident (key, rule, severity, title, body, opened_at, "
                     "last_seen_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                     (key, rule, severity, title, body, at, at))


@pytest.fixture
def alerts(store):
    ai.ensure_tables(store)
    ai.set_switches(store, {"explainer": True})
    open_incident(store, "outside:transip", "outside", "warning", "TransIP: incident",
                  "Reported by admin@example.org", hours=5)
    open_incident(store, "disk_space:volume2", "disk_space", "warning", "volume2 is 91% full")
    open_incident(store, "train:x", "train", "warning", "Tomorrow, on your route: A - B")
    return store


def test_a_button_only_with_open_alerts_and_the_switch_on(store, alerts):
    assert explain_open.buttons(CFG, alerts) == [explain_open.BUTTON]

    ai.set_switches(alerts, {"explainer": False})
    assert explain_open.buttons(CFG, alerts) is None


def test_train_alerts_alone_get_no_button(store):
    ai.ensure_tables(store)
    ai.set_switches(store, {"explainer": True})
    open_incident(store, "train:x", "train", "warning", "Tomorrow, on your route: A - B")

    assert explain_open.buttons(CFG, store) is None


def test_explains_each_open_alert_as_a_reply(alerts):
    claude, telegram = FakeClaude(), FakeTelegram()

    sent = asyncio.run(explain_open.explain(CFG, alerts, "nas", 42, NOW, claude,
                                            telegram.client()))

    (call,) = claude.calls
    assert call["model"] == "claude-sonnet-5-5"
    prompt = call["messages"][0]["content"]
    assert "1. [WARNING, open 5 h 0 min] TransIP: incident\n   Reported by <email>" in prompt
    assert "2. [WARNING, open 2 h 0 min] volume2 is 91% full" in prompt
    assert "Tomorrow" not in prompt and "admin@example.org" not in prompt
    ((method, payload),) = telegram.calls
    assert method == "sendMessage" and payload["chat_id"] == "-1"
    assert payload["reply_parameters"]["message_id"] == 42
    assert payload["text"] == (
        "<b>Open alerts, explained</b>\n\n"
        "<b>TransIP: incident</b>\nTransIP reports an outage.\n<i>Try</i> · Nothing; it should "
        "pass.\n\n"
        "<b>volume2 is 91% full</b>\nThe downloads pool is nearly full.\n<i>Try</i> · Clear "
        "finished downloads.")
    assert sent.status == "sent"


def test_nothing_open_any_more_needs_no_claude(store):
    ai.ensure_tables(store)
    claude, telegram = FakeClaude(), FakeTelegram()

    asyncio.run(explain_open.explain(CFG, store, "nas", 42, NOW, claude, telegram.client()))

    assert claude.calls == []
    assert telegram.calls[0][1]["text"] == "Nothing is open any more."


def test_no_answer_sends_nothing(alerts):
    telegram = FakeTelegram()

    assert asyncio.run(explain_open.explain(CFG, alerts, "nas", 42, NOW, FakeClaude("nope"),
                                            telegram.client())) is None
    assert telegram.calls == []


def tap(chat="-1", data=explain_open.CALLBACK):
    return {"update_id": 7, "callback_query": {
        "id": "cb1", "data": data, "from": {"first_name": "Pim"},
        "message": {"message_id": 42, "chat": {"id": int(chat)}}}}


def test_the_bot_answers_a_tap_then_replies_to_the_briefing(alerts, monkeypatch):
    claude, telegram = FakeClaude(), FakeTelegram()
    monkeypatch.setattr(ai, "_client", claude)

    assert asyncio.run(bot.handle_update(alerts, CFG, tap(), telegram.client(), "HubBot"))

    assert [m for m, _ in telegram.calls] == ["answerCallbackQuery", "sendMessage"]
    assert telegram.calls[0][1] == {"callback_query_id": "cb1", "text": "Asking Claude..."}
    assert telegram.calls[1][1]["reply_parameters"]["message_id"] == 42


def test_the_bot_says_so_when_claude_does_not_answer(alerts, monkeypatch):
    telegram = FakeTelegram()
    monkeypatch.setattr(ai, "_client", FakeClaude("nope"))

    asyncio.run(bot.handle_update(alerts, CFG, tap(), telegram.client(), "HubBot"))

    assert telegram.calls[1][1]["text"] == (
        "<b>INFO</b> · <b>Claude did not answer</b>\nThe alerts are on the Alerts page.")


def test_taps_from_elsewhere_or_other_buttons_are_ignored(alerts):
    telegram = FakeTelegram()

    for update in (tap(chat="-99"), tap(data="something")):
        assert not asyncio.run(bot.handle_update(alerts, CFG, update, telegram.client(), None))
    assert telegram.calls == []
