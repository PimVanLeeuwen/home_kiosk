from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from types import SimpleNamespace

import httpx
import pytest

from app import ai, explainer
from app.alerts import core, rules
from app.alerts.core import AlertMessage
from app.alerts.telegram import Telegram

CFG = {
    "timezone": "Europe/Amsterdam",
    "nas": {"docker_socket": "/var/run/docker.sock"},
    "ai": {"api_key": "sk-test"},
    "telegram": {"token": "t", "chats": {"nas": {"id": "-1", "label": "NAS"}}},
}
NOW = datetime(2026, 10, 25, 12, 0, tzinfo=UTC)
ANSWER = {"cause": "The database ran out of disk space: \"No space left on device\".",
          "steps": ["Free space on volume2.", "Restart tracearr-db.", "", "A fourth is cut.",
                    "So is a fifth."]}


def frame(stream: int, text: str) -> bytes:
    data = text.encode()
    return bytes([stream, 0, 0, 0]) + len(data).to_bytes(4, "big") + data


LOGS = (frame(1, "2026-10-25T11:58:01Z starting tracearr, admin pim@example.org\n")
        + frame(2, "2026-10-25T11:58:02Z connect to 192.168.1.20:5432 failed\n")
        + frame(2, "2026-10-25T11:58:03Z FATAL: could not extend file: No space left on device\n"))
INSPECT = {"State": {"Status": "restarting", "ExitCode": 1, "OOMKilled": False, "Error": "",
                     "Health": {"Log": [{"Output": "pg_isready: no response"}]}},
           "RestartCount": 4, "Config": {"Image": "postgres:16-alpine"}}


def docker(seen=None):
    def handler(request):
        if seen is not None:
            seen.append(request)
        if request.url.path.endswith("/logs"):
            return httpx.Response(200, content=LOGS)
        return httpx.Response(200, json=INSPECT)

    return httpx.MockTransport(handler)


class FakeClaude:
    """Answers on the beta path (Sonnet's fallback) and records what it was sent."""

    def __init__(self, answer=ANSWER, model="claude-sonnet-5-5"):
        self.answer, self.model, self.calls = answer, model, []

    def __call__(self, api_key):
        create = self.create
        return SimpleNamespace(beta=SimpleNamespace(messages=SimpleNamespace(create=create)),
                               messages=SimpleNamespace(create=create))

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        usage = SimpleNamespace(input_tokens=6000, output_tokens=300,
                                cache_read_input_tokens=0, cache_creation_input_tokens=0)
        return SimpleNamespace(stop_reason="end_turn", usage=usage, model=self.model,
                               content=[SimpleNamespace(type="text", text=json.dumps(self.answer))])


class Sent:
    def __init__(self):
        self.payloads = []

    def client(self):
        def handler(request):
            self.payloads.append(json.loads(request.content))
            return httpx.Response(200, json={"ok": True, "result": {"message_id": 778}})

        return Telegram("t", transport=httpx.MockTransport(handler))


@pytest.fixture
def on(store):
    ai.ensure_tables(store)
    core.ensure_tables(store)
    rules.ensure_tables(store)
    ai.set_switches(store, {"explainer": True})
    store.put_cache("nas", {"storage": {"pools": [{"name": "volume2", "used_pct": 99.2}]},
                            "ram_pct": 41})
    return store


def alert(**over):
    fields = {"id": 1, "ts": NOW, "source": "rule.container_health", "category": "rules",
              "severity": "error", "title": "tracearr-db is down", "body": "", "chat": "nas",
              "status": "sent", "error": None, "sent_at": NOW, "telegram_id": 555}
    return AlertMessage.model_validate(fields | over)


def explain(store, claude, sent, message=None, seen=None):
    return asyncio.run(explainer.explain(CFG, store, "tracearr-db is down", "tracearr-db",
                                         message or alert(), NOW, docker(seen), claude,
                                         sent.client()))


def test_redacts_people_addresses_and_secrets():
    text = ("user pim@example.org from 192.168.1.20 and fe80::1ff:fe23:4567:890a, "
            "mac aa:bb:cc:dd:ee:ff, postgres://hub:hunter2@db:5432/x, "
            "Authorization: Bearer abc.def-ghi, api_key=sk-12345 password: \"s3cret\", "
            "jwt eyJhbGciOi.eyJzdWIi.c2lnbmF0dXJl, "
            "token 0123456789abcdef0123456789abcdef01234567")

    clean = explainer.redact(text)

    for leaked in ("pim@example.org", "192.168.1.20", "fe80::", "aa:bb:cc", "hunter2", "abc.def",
                   "sk-12345", "s3cret", "eyJhbGciOi", "0123456789abcdef0123"):
        assert leaked not in clean
    assert "postgres://<secret>@db:5432/x" in clean
    assert "at 12:30:45 on 2026-10-25" == explainer.redact("at 12:30:45 on 2026-10-25")
    assert explainer.redact("listening on ::1 and [::]:8080") == "listening on <ip> and [<ip>]:8080"
    assert explainer.redact("std::vector") == "std::vector"


def test_reads_dockers_log_stream_with_and_without_its_headers():
    assert explainer.demux(frame(1, "a\n") + frame(2, "b\n")) == "a\nb\n"
    assert explainer.demux(b"plain tty output\n") == "plain tty output\n"


def test_asks_sonnet_with_its_fallback_and_only_redacted_logs(on):
    claude, seen = FakeClaude(), []

    explain(on, claude, Sent(), seen=seen)

    call = claude.calls[0]
    assert call["model"] == "claude-sonnet-5-5"
    assert call["betas"] == ["server-side-fallback-2026-07-01"] and call["fallbacks"] == "default"
    assert call["output_config"]["effort"] == "medium"
    prompt = call["messages"][0]["content"]
    assert "Status: restarting, exit code 1" in prompt and "Restarts: 4" in prompt
    assert "Last health check: pg_isready: no response" in prompt
    assert "Storage: volume2 99% full" in prompt and "Memory in use: 41%" in prompt
    assert "No space left on device" in prompt
    assert "pim@example.org" not in prompt and "192.168.1.20" not in prompt
    assert seen[1].url.params["tail"] == "200"


def test_replies_to_the_alert_with_the_cause_and_up_to_three_steps(on):
    sent = Sent()

    explain(on, FakeClaude(), sent)

    (payload,) = sent.payloads
    assert payload["reply_parameters"] == {"message_id": 555, "allow_sending_without_reply": True}
    assert payload["text"] == (
        "<b>Likely cause</b> · tracearr-db\n"
        "The database ran out of disk space: \"No space left on device\".\n"
        "<b>Try first</b>\n1. Free space on volume2.\n2. Restart tracearr-db.\n"
        "3. A fourth is cut.")
    logged = core.messages(on, 10)[0]
    assert logged.source == "explainer" and logged.telegram_id == 778


def test_says_nothing_for_a_held_alert_or_with_the_switch_off(on):
    claude, sent = FakeClaude(), Sent()

    assert explain(on, claude, sent, alert(status="held", telegram_id=None)) is None
    ai.set_switches(on, {"explainer": False})
    assert explain(on, claude, sent) is None
    assert claude.calls == [] and sent.payloads == []


def test_a_fallback_answer_is_counted_at_its_own_price(on):
    explain(on, FakeClaude(model="claude-opus-4-8"), Sent())

    with on.connect() as conn:
        row = conn.execute("SELECT model, cost_usd FROM ai_usage").fetchone()
    assert row["model"] == "claude-opus-4-8"
    assert row["cost_usd"] == pytest.approx((6000 * 5 + 300 * 25) / 1_000_000)


def test_only_container_alerts_that_went_out_are_explained(on, monkeypatch):
    asked = []

    async def fake(*args, **kwargs):
        asked.append(args[3])

    monkeypatch.setattr(explainer, "explain", fake)
    monkeypatch.setattr(explainer, "DELAY_SECONDS", 0)
    down = rules.Problem("down:tracearr-db", "container_health", "error", "container_down",
                         {"service": "Tracearr", "container": "tracearr-db", "state": "exited"})
    disk = rules.Problem("disk_space:volume2", "disk_space", "warning", "disk_space",
                         {"pool": "volume2", "used_pct": 95})

    async def scenario():
        explainer.later(CFG, on, down, alert())
        explainer.later(CFG, on, disk, alert())
        explainer.later(CFG, on, down, alert(status="held", telegram_id=None))
        await asyncio.sleep(0.05)

    asyncio.run(scenario())
    assert asked == ["tracearr-db"]
