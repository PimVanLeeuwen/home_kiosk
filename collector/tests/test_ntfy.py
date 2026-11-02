"""ntfy as the hub's first channel, with Telegram as the fallback (plan.md M31)."""

from __future__ import annotations

import asyncio
import json
import logging
import sqlite3
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from fastapi.testclient import TestClient

from app import main
from app.alerts import core
from app.alerts import ntfy as ntfy_api
from app.alerts.ntfy import Ntfy, NtfyError
from app.alerts.telegram import Telegram

NTFY_TOKEN = "tk_secretsecretsecretsecretsec"
CFG = {
    "timezone": "Europe/Amsterdam",
    "hub": {"url": "https://hub.example.ts.net/"},
    "ntfy": {"url": "http://ntfy.test:8090", "token": NTFY_TOKEN},
    "telegram": {
        "token": "123456:SECRET-bot-token",
        "chats": {
            "nas": {"id": "-1001", "label": "NAS alerts"},
            "portfolio": {"id": "-1002", "label": "Portfolio"},
        },
    },
}
# 12:00 and 01:00 in Amsterdam (UTC+2 in summer); 06:30 for the briefing.
NOON = datetime(2026, 9, 30, 10, 0, tzinfo=UTC)
NIGHT = datetime(2026, 9, 30, 23, 0, tzinfo=UTC)
BRIEFING = datetime(2026, 10, 1, 4, 30, tzinfo=UTC)


class FakeNtfy:
    """Records published messages; can be told to fail."""

    def __init__(self, status=200):
        self.published, self.headers, self.status = [], [], status

    def client(self):
        def handler(request):
            self.headers.append(request.headers)
            self.published.append(json.loads(request.content))
            if self.status != 200:
                return httpx.Response(self.status, json={"error": "forbidden"})
            return httpx.Response(200, json={"id": "abc123XYZ", "event": "message"})

        return Ntfy(CFG["ntfy"]["url"], NTFY_TOKEN, transport=httpx.MockTransport(handler))


class FakeTelegram:
    def __init__(self, status=200):
        self.sent, self.status = [], status

    def client(self):
        def handler(request):
            self.sent.append(json.loads(request.content))
            return httpx.Response(self.status, json={"ok": True, "result": {"message_id": 7}})

        return Telegram(CFG["telegram"]["token"], transport=httpx.MockTransport(handler))


@pytest.fixture
def alert_store(store):
    core.ensure_tables(store)
    return store


def notify(store, ntfy=None, telegram=None, **fields):
    defaults = {"source": "backup", "category": "backup", "severity": "warning",
                "title": "Backup slow", "body": "Volume 3 took 4 hours.", "now": NOON}
    return asyncio.run(core.notify(
        store, CFG, ntfy=ntfy.client() if ntfy else None,
        telegram=(telegram or FakeTelegram()).client(), **(defaults | fields)))


# --- the client --------------------------------------------------------------------


def test_plain_drops_tags_and_keeps_text_links_and_table_lines():
    text = ('<b>Markets</b> &amp; more\n<pre>NVDA  +2.1%\nASML  -0.4%</pre>\n\n\n\n'
            '<a href="https://nos.nl/x">Rates &quot;up&quot;</a>')

    assert ntfy_api.plain(text) == 'Markets & more\nNVDA  +2.1%\nASML  -0.4%\n\nRates "up"'


def test_clip_cuts_on_bytes_and_characters():
    assert ntfy_api.clip("short") == "short"
    clipped = ntfy_api.clip("é" * 10, limit=9)
    assert clipped == "ééé…" and len(clipped.encode()) <= 9


def test_the_client_needs_an_address_and_a_token():
    with pytest.raises(NtfyError, match="NTFY_TOKEN"):
        Ntfy("http://ntfy.test", " ")
    with pytest.raises(NtfyError, match="ntfy.url"):
        Ntfy("", NTFY_TOKEN)


@pytest.mark.parametrize(("exc", "reason"), [
    (httpx.ConnectError("x"), "ntfy not reachable"),
    (httpx.ReadTimeout("x"), "ntfy timed out"),
    (NtfyError("No ntfy token set (NTFY_TOKEN)"), "No ntfy token set (NTFY_TOKEN)"),
    (ValueError("x"), "Unexpected answer from ntfy"),
])
def test_failures_become_a_short_reason(exc, reason):
    assert ntfy_api.describe(exc) == reason


# --- sending -----------------------------------------------------------------------


def test_a_message_goes_to_its_category_topic_with_a_dot_and_its_page(alert_store):
    fake, telegram = FakeNtfy(), FakeTelegram()

    message = notify(alert_store, fake, telegram)

    assert fake.published == [{
        "topic": "hub-backup", "title": "Backup slow", "message": "Volume 3 took 4 hours.",
        "priority": 3, "tags": ["orange_circle"],
        "click": f"https://hub.example.ts.net/alerts/{message.id}",
    }]
    assert fake.headers[0]["authorization"] == f"Bearer {NTFY_TOKEN}"
    assert telegram.sent == []
    assert (message.status, message.channel, message.ntfy_id) == ("sent", "ntfy", "abc123XYZ")


def test_a_template_sends_its_text_without_the_title_line(alert_store):
    fake = FakeNtfy()
    formatted = "<b>WARNING</b> · <b>Backup slow</b>\n<i>Volume 3</i> took &lt;4h&gt;"

    notify(alert_store, fake, formatted=formatted)

    assert fake.published[0]["message"] == "Volume 3 took <4h>"


def test_a_title_alone_goes_as_the_message_under_the_category(alert_store):
    fake = FakeNtfy()

    notify(alert_store, fake, severity="ok", title="NAS backup OK", body="")

    assert fake.published[0] | {"click": None} == {
        "topic": "hub-backup", "title": "Backups", "message": "NAS backup OK",
        "priority": 3, "tags": ["green_circle"], "click": None}


@pytest.mark.parametrize(("fields", "priority", "status"), [
    ({"severity": "error"}, 4, "sent"),  # Time Sensitive, day or night
    ({"severity": "error", "now": NIGHT}, 4, "sent"),
    ({"now": NIGHT}, 2, "quiet"),  # silently instead of held
    ({"now": NIGHT, "bypass_quiet": True}, 3, "sent"),  # the train, a typed message
    ({"now": BRIEFING, "category": "briefing", "bypass_quiet": True}, 2, "sent"),
])
def test_priority_follows_severity_and_quiet_hours(alert_store, fields, priority, status):
    fake = FakeNtfy()

    message = notify(alert_store, fake, **fields)

    assert fake.published[0]["priority"] == priority
    assert message.status == status


def test_a_failed_ntfy_falls_back_to_telegram_and_says_so(alert_store, caplog):
    fake, telegram = FakeNtfy(status=403), FakeTelegram()

    with caplog.at_level(logging.DEBUG):
        message = notify(alert_store, fake, telegram)

    assert len(telegram.sent) == 1 and telegram.sent[0]["chat_id"] == "-1001"
    assert (message.status, message.channel, message.telegram_id) == ("sent", "telegram", 7)
    assert message.error == "ntfy failed: ntfy answered 403: forbidden"
    assert NTFY_TOKEN not in caplog.text


def test_a_failed_ntfy_at_night_is_held_for_the_telegram_digest(alert_store):
    telegram = FakeTelegram()

    message = notify(alert_store, FakeNtfy(status=500), telegram, now=NIGHT)

    assert telegram.sent == []
    assert message.status == "held" and message.error.startswith("ntfy failed")


def test_both_channels_failing_logs_both_reasons(alert_store):
    message = notify(alert_store, FakeNtfy(status=500), FakeTelegram(status=500))

    assert message.status == "failed" and message.channel is None
    assert message.error.startswith("ntfy: ntfy answered 500") and "Telegram: " in message.error


def test_replies_to_a_telegram_message_stay_on_telegram(alert_store):
    fake, telegram = FakeNtfy(), FakeTelegram()

    message = notify(alert_store, fake, telegram, reply_to=42)

    assert fake.published == []
    assert message.channel == "telegram"
    assert telegram.sent[0]["reply_parameters"]["message_id"] == 42


def test_ntfy_is_on_with_a_token_until_switched_off(alert_store):
    assert core.ntfy_on(alert_store, CFG)
    assert not core.ntfy_on(alert_store, {**CFG, "ntfy": {"url": "http://ntfy.test", "token": ""}})

    core.put_setting(alert_store, "ntfy", False)

    assert not core.ntfy_on(alert_store, CFG)


def test_with_ntfy_off_messages_go_to_telegram(alert_store):
    telegram = FakeTelegram()
    core.put_setting(alert_store, "ntfy", False)

    message = asyncio.run(core.notify(
        alert_store, CFG, source="backup", category="backup", severity="info",
        title="Backup OK", now=NOON, telegram=telegram.client()))

    assert message.channel == "telegram" and len(telegram.sent) == 1


def test_the_tap_needs_a_web_address():
    assert core.click_url({"hub": {"url": "https://hub.example.ts.net"}}, 12) == (
        "https://hub.example.ts.net/alerts/12")
    assert core.click_url({"hub": {"url": "https://hub.example.ts.net"}}) == (
        "https://hub.example.ts.net/alerts")
    assert core.click_url({"hub": {"url": "javascript:alert(1)"}}) is None
    assert core.click_url({}) is None


# --- the night, for the briefing ---------------------------------------------------


def test_quiet_since_lists_the_nights_silent_messages_for_a_chat(alert_store):
    fake = FakeNtfy()
    notify(alert_store, fake, now=NIGHT, title="Disk warm")
    notify(alert_store, fake, now=NIGHT, category="portfolio", title="NVDA -6%")
    notify(alert_store, fake, now=NIGHT - timedelta(days=1), title="Yesterday's")
    notify(alert_store, fake, now=NOON, title="Daytime")

    night = core.quiet_since(alert_store, BRIEFING - timedelta(hours=12), "nas")

    assert [m["title"] for m in night] == ["Disk warm"]


def test_older_rows_are_marked_as_sent_through_telegram(store):
    with store.connect() as conn:
        # The log as it was before ntfy: without its columns.
        conn.execute("DROP TABLE IF EXISTS alert_message")
        conn.executescript(core.TABLES)
        conn.execute("INSERT INTO alert_message (ts, source, category, severity, title, chat, "
                     "status) VALUES ('2026-09-01T10:00:00+00:00', 'backup', 'backup', 'ok', "
                     "'Old', 'nas', 'sent')")

    core.ensure_tables(store)

    with store.connect() as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT channel, ntfy_id FROM alert_message").fetchone()
    assert (row["channel"], row["ntfy_id"]) == ("telegram", None)


# --- the setting -------------------------------------------------------------------


@pytest.fixture
def client(alert_store):
    main.app.state.store = alert_store
    main.app.state.config = CFG
    return TestClient(main.app)


def test_settings_show_and_switch_ntfy(client):
    origin = {"origin": "http://testserver"}
    settings = client.get("/api/alerts/settings").json()
    assert settings["ntfy"] == {"configured": True, "enabled": True}
    body = {"routing": settings["routing"], "quiet": settings["quiet"]}

    off = client.put("/api/alerts/settings", json=body | {"ntfy": False}, headers=origin)
    kept = client.put("/api/alerts/settings", json=body, headers=origin)

    assert off.json()["ntfy"] == {"configured": True, "enabled": False}
    assert kept.json()["ntfy"]["enabled"] is False
