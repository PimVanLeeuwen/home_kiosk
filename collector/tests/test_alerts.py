from __future__ import annotations

import asyncio
import json
import logging
from datetime import UTC, datetime

import httpx
import pytest
from fastapi.testclient import TestClient

from app import main
from app.alerts import core
from app.alerts.telegram import Telegram

TOKEN = "123456:SECRET-bot-token"
KEY = "notify-key-xyz"
CFG = {
    "timezone": "Europe/Amsterdam",
    "telegram": {
        "token": TOKEN,
        "notify_key": KEY,
        "chats": {
            "nas": {"id": "-1001", "label": "NAS alerts"},
            "portfolio": {"id": "-1002", "label": "Portfolio"},
        },
    },
}
# 12:00 and 01:00 in Amsterdam (UTC+2 in summer).
NOON = datetime(2026, 9, 30, 10, 0, tzinfo=UTC)
NIGHT = datetime(2026, 9, 30, 23, 0, tzinfo=UTC)
MORNING = datetime(2026, 10, 1, 5, 10, tzinfo=UTC)  # 07:10 local


class FakeTelegram:
    """Records sendMessage calls; can be told to fail."""

    def __init__(self, status=200, body=None):
        self.sent = []
        self.status, self.body = status, body or {"ok": True, "result": {}}

    def transport(self):
        def handler(request):
            self.sent.append((request.url.path, json.loads(request.content)))
            return httpx.Response(self.status, json=self.body)

        return httpx.MockTransport(handler)

    def client(self):
        return Telegram(TOKEN, transport=self.transport())


@pytest.fixture
def alert_store(store):
    core.ensure_tables(store)
    return store


def notify(store, fake, **fields):
    defaults = {
        "source": "backup",
        "category": "backup",
        "severity": "info",
        "title": "Backup OK",
        "now": NOON,
    }
    return asyncio.run(core.notify(store, CFG, telegram=fake.client(), **(defaults | fields)))


def test_format_html_escapes_text_and_adds_the_level():
    assert core.format_html("error", "Disk <sda> failing", "a & b") == (
        "<b>ERROR</b> · <b>Disk &lt;sda&gt; failing</b>\na &amp; b"
    )


@pytest.mark.parametrize(
    ("hm", "quiet", "expected"),
    [
        ("23:30", {"enabled": True, "start": "23:00", "end": "07:00"}, True),
        ("06:59", {"enabled": True, "start": "23:00", "end": "07:00"}, True),
        ("07:00", {"enabled": True, "start": "23:00", "end": "07:00"}, False),
        ("12:00", {"enabled": True, "start": "23:00", "end": "07:00"}, False),
        ("13:00", {"enabled": True, "start": "12:00", "end": "14:00"}, True),
        ("23:30", {"enabled": False, "start": "23:00", "end": "07:00"}, False),
        ("23:30", {"enabled": True, "start": "07:00", "end": "07:00"}, False),
    ],
)
def test_quiet_hours(hm, quiet, expected):
    hour, minute = map(int, hm.split(":"))
    assert core.in_quiet_hours(datetime(2026, 10, 1, hour, minute), quiet) is expected


def test_notify_sends_html_to_the_routed_chat_and_logs_it(alert_store):
    fake = FakeTelegram()

    message = notify(alert_store, fake, severity="ok", title="NAS backup OK", body="volume1 4 min")

    assert (message.status, message.chat, message.error) == ("sent", "nas", None)
    path, payload = fake.sent[0]
    assert path == f"/bot{TOKEN}/sendMessage"
    assert payload == {
        "chat_id": "-1001",
        "text": "<b>OK</b> · <b>NAS backup OK</b>\nvolume1 4 min",
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
        "disable_notification": False,
    }
    assert [m.title for m in core.messages(alert_store)] == ["NAS backup OK"]


def test_routing_is_editable_per_category(alert_store):
    core.put_setting(alert_store, "routing", {"backup": "portfolio"})
    fake = FakeTelegram()

    notify(alert_store, fake)

    assert fake.sent[0][1]["chat_id"] == "-1002"


def test_quiet_hours_hold_all_but_errors(alert_store):
    fake = FakeTelegram()

    held = notify(alert_store, fake, severity="warning", title="Pool 91% full", now=NIGHT)
    urgent = notify(alert_store, fake, severity="error", title="Backup failed", now=NIGHT)

    assert (held.status, urgent.status) == ("held", "sent")
    assert [p["text"] for _, p in fake.sent] == ["<b>ERROR</b> · <b>Backup failed</b>"]


def test_digest_after_quiet_hours_sends_held_messages_once(alert_store):
    fake = FakeTelegram()
    notify(alert_store, fake, severity="warning", title="Pool 91% full", now=NIGHT)
    notify(alert_store, fake, severity="info", title="3 images updated", now=NIGHT)

    # Still night: nothing yet.
    assert asyncio.run(core.send_digests(alert_store, CFG, NIGHT, fake.client())) == 0
    assert asyncio.run(core.send_digests(alert_store, CFG, MORNING, fake.client())) == 1
    assert asyncio.run(core.send_digests(alert_store, CFG, MORNING, fake.client())) == 0

    ((_, digest),) = fake.sent
    assert digest["text"] == (
        "<b>While you slept (2)</b>\nWARNING · Pool 91% full\nINFO · 3 images updated")
    assert {m.status for m in core.messages(alert_store)} == {"digested"}


def test_a_failed_digest_stays_held_for_the_next_try(alert_store):
    notify(alert_store, FakeTelegram(), severity="info", title="x", now=NIGHT)

    assert (
        asyncio.run(core.send_digests(alert_store, CFG, MORNING, FakeTelegram(500).client())) == 0
    )
    assert core.messages(alert_store)[0].status == "held"


def test_failures_are_logged_with_a_short_reason(alert_store, caplog):
    refused = FakeTelegram(403, {"ok": False, "description": "Forbidden: bot was kicked"})
    with caplog.at_level(logging.DEBUG):
        message = notify(alert_store, refused)

    assert message.status == "failed"
    assert message.error == "Telegram answered 403: Forbidden: bot was kicked"
    assert TOKEN not in caplog.text and TOKEN not in message.model_dump_json()

    no_chat = asyncio.run(
        core.notify(
            alert_store,
            {**CFG, "telegram": {**CFG["telegram"], "chats": {}}},
            source="x",
            category="backup",
            severity="info",
            title="t",
            now=NOON,
            telegram=FakeTelegram().client(),
        )
    )
    assert (no_chat.status, no_chat.error) == ("failed", "No chat id set for nas")


def test_a_missing_token_is_a_failed_message_not_a_crash(alert_store):
    cfg = {**CFG, "telegram": {**CFG["telegram"], "token": ""}}
    message = asyncio.run(
        core.notify(
            alert_store, cfg, source="x", category="backup", severity="info", title="t", now=NOON
        )
    )

    assert (message.status, message.error) == ("failed", "No bot token set (TELEGRAM_BOT_TOKEN)")


# --- endpoints ---------------------------------------------------------------------


@pytest.fixture
def client(alert_store, monkeypatch):
    fake = FakeTelegram()
    monkeypatch.setattr(core, "Telegram", lambda token: Telegram(token, transport=fake.transport()))
    main.app.state.store = alert_store
    main.app.state.config = CFG
    test_client = TestClient(main.app)
    test_client.fake = fake
    return test_client


POST = {"source": "backup", "category": "backup", "severity": "ok", "title": "NAS backup OK"}


def test_notify_needs_the_shared_key(client):
    assert client.post("/api/notify", json=POST).status_code == 401
    assert (
        client.post("/api/notify", json=POST, headers={"X-Notify-Key": "wrong"}).status_code == 401
    )

    ok = client.post("/api/notify", json=POST, headers={"X-Notify-Key": KEY})
    assert ok.status_code == 200
    assert ok.json()["status"] in ("sent", "held")


def test_notify_takes_paperless_new_senders_to_the_nas_chat(client):
    post = {"source": "paperless", "category": "paperless", "severity": "info",
            "title": "2 new senders for Paperless", "body": "energie-nieuw.nl: 3 PDFs"}

    resp = client.post("/api/notify", json=post, headers={"X-Notify-Key": KEY})

    assert resp.status_code == 200
    assert client.get("/api/alerts/settings").json()["routing"]["paperless"] == "nas"


def test_notify_is_closed_when_no_key_is_configured(client):
    main.app.state.config = {**CFG, "telegram": {**CFG["telegram"], "notify_key": ""}}

    resp = client.post("/api/notify", json=POST, headers={"X-Notify-Key": ""})

    assert resp.status_code == 503


@pytest.mark.parametrize(
    "change",
    [{"category": "nope"}, {"severity": "panic"}, {"title": ""}, {"source": "Bad Source!"}],
)
def test_notify_validates(client, change):
    resp = client.post("/api/notify", json=POST | change, headers={"X-Notify-Key": KEY})

    assert resp.status_code == 422


def test_settings_round_trip_and_validation(client):
    settings = client.get("/api/alerts/settings").json()
    assert settings["routing"]["portfolio"] == "portfolio"
    assert settings["token_set"] is True and settings["notify_key_set"] is True
    assert [c["key"] for c in settings["chats"]] == ["nas", "portfolio"]

    body = {
        "routing": {"backup": "portfolio"},
        "quiet": {"enabled": False, "start": "22:00", "end": "06:30"},
    }
    origin = {"origin": "http://testserver"}
    saved = client.put("/api/alerts/settings", json=body, headers=origin).json()
    assert saved["routing"]["backup"] == "portfolio"
    assert saved["quiet"] == {"enabled": False, "start": "22:00", "end": "06:30"}

    bad_chat = {**body, "routing": {"backup": "elsewhere"}}
    bad_time = {**body, "quiet": {"enabled": True, "start": "25:00", "end": "06:30"}}
    assert client.put("/api/alerts/settings", json=bad_chat, headers=origin).status_code == 422
    assert client.put("/api/alerts/settings", json=bad_time, headers=origin).status_code == 422
    assert (
        client.put(
            "/api/alerts/settings", json=body, headers={"origin": "https://evil.example"}
        ).status_code
        == 403
    )


def test_manual_messages_go_to_the_chosen_chat_right_away(client):
    resp = client.post(
        "/api/alerts/send",
        json={"chat": "portfolio", "text": "Hello\nfrom the hub"},
        headers={"origin": "http://testserver"},
    )

    assert resp.json()["status"] == "sent"
    _, payload = client.fake.sent[0]
    assert payload["chat_id"] == "-1002"
    assert payload["text"] == "<b>INFO</b> · <b>Hello</b>\nfrom the hub"
    assert client.get("/api/alerts/messages").json()[0]["category"] == "manual"


def test_watchtower_reports_get_their_summary_line_as_title(client):
    # What Shoutrrr's generic service posts for Watchtower: template=json,
    # messagekey=body, plus the $source/$category/$severity extra fields.
    report = (
        "🔄 Watchtower: 36 scanned, 2 updated, 0 failed\n✅ sonarr (lscr.io/linuxserver/sonarr)"
    )
    resp = client.post(
        "/api/notify",
        json={
            "title": "",
            "body": report,
            "source": "watchtower",
            "category": "updates",
            "severity": "info",
        },
        headers={"X-Notify-Key": KEY},
    )

    message = resp.json()
    assert resp.status_code == 200
    assert message["title"] == "Watchtower: 36 scanned, 2 updated, 0 failed"
    assert message["body"] == "Updated sonarr (lscr.io/linuxserver/sonarr)"


@pytest.mark.parametrize(
    ("payload", "expected"),
    [
        (
            {
                "heartbeat": {"status": 0, "msg": "connect ECONNREFUSED"},
                "monitor": {"name": "Jellyfin"},
                "msg": "[Jellyfin] [🔴 Down]",
            },
            ("error", "Jellyfin is down", "connect ECONNREFUSED"),
        ),
        (
            {
                "heartbeat": {"status": 1, "msg": "200 - OK"},
                "monitor": {"name": "Jellyfin"},
                "msg": "[Jellyfin] [✅ Up]",
            },
            ("ok", "Jellyfin is up", "200 - OK"),
        ),
        (
            {"heartbeat": None, "monitor": None, "msg": "Uptime Kuma Webhook testing"},
            ("info", "Uptime Kuma", "Uptime Kuma Webhook testing"),
        ),
    ],
)
def test_uptime_kuma_webhooks_are_translated(client, payload, expected):
    resp = client.post("/api/notify/kuma", json=payload, headers={"X-Notify-Key": KEY})

    m = resp.json()
    assert (m["severity"], m["title"], m["body"]) == expected
    assert (m["source"], m["category"]) == ("uptime-kuma", "uptime")


def test_uptime_kuma_webhooks_need_the_key(client):
    assert client.post("/api/notify/kuma", json={"msg": "x"}).status_code == 401
