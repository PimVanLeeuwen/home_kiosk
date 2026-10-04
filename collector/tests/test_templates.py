from __future__ import annotations

import asyncio

import pytest
from fastapi.testclient import TestClient

from app import main
from app.alerts import core, formats, templates

KEY = "notify-secret"
CFG = {
    "timezone": "Europe/Amsterdam",
    "telegram": {"token": "t", "notify_key": KEY,
                 "chats": {"nas": {"id": "-1001"}, "portfolio": {"id": "-1002"}}},
}
SAME_ORIGIN = {"Origin": "http://testserver", "Content-Type": "application/json"}


class FakeTelegram:
    def __init__(self):
        self.sent = []

    async def send(self, chat_id, text):
        self.sent.append((chat_id, text))


@pytest.fixture(autouse=True)
def tables(store):
    core.ensure_tables(store)


@pytest.fixture
def client(store, monkeypatch):
    main.app.state.store = store
    main.app.state.config = CFG
    fake = FakeTelegram()
    monkeypatch.setattr(core, "Telegram", lambda token: fake)
    c = TestClient(main.app)
    c.fake = fake
    return c


# --- rendering ---------------------------------------------------------------------


def test_defaults_give_the_old_messages(store):
    assert templates.render(store, "disk_space", {
        "pool": "volume2", "used_pct": 92, "free": "1,4 TB", "total": "17,9 TB"}, "warning") == (
        core.format_html("warning", "volume2 is 92% full", "1,4 TB left of 17,9 TB"))
    # An empty body line is left out, like format_html without a body.
    assert templates.render(store, "kuma", {"monitor": "Jellyfin", "state": "is up",
                                            "message": ""}, "ok") == (
        core.format_html("ok", "Jellyfin is up"))


def test_values_are_escaped_and_only_safe_tags_kept(store):
    templates.save(store, "kuma", "{icon} <b>{monitor}</b> <i>{state}</i> & <code>{message}</code>")
    text = templates.render(store, "kuma", {"monitor": "<script>", "state": "is down",
                                            "message": "a & b"}, "error")
    assert text == "❌ <b>&lt;script&gt;</b> <i>is down</i> &amp; <code>a &amp; b</code>"


def test_blocks_repeat_their_line_template_and_vanish_when_empty(store):
    templates.save(store, "backup_volume", "{status} {name}")
    values = {"minutes": 5, "volumes": [{"status": "✅", "name": "volume1", "label": "x"},
                                        {"status": "❌", "name": "volume3", "label": "y"}]}
    assert templates.render(store, "backup_failed", values, "error") == (
        "❌ <b>NAS backup FAILED</b>\n✅ volume1\n❌ volume3\n⏱ 5 min, see the Backups page")
    assert templates.render(store, "backup_ok", {"minutes": 5, "volumes": []}, "ok") == (
        "✅ <b>NAS backup OK</b>\n⏱ 5 min")


def test_message_splits_a_plain_title_and_body_for_the_log(store):
    sent = templates.message(store, "container_down", {
        "service": "Jellyfin", "container": "jellyfin", "state": "exited"}, "error")
    assert (sent.title, sent.body) == ("Jellyfin is down", "container jellyfin: exited")


def test_save_only_keeps_changes_and_reset_removes_them(store):
    templates.save(store, "kuma", "{icon} {monitor} {state}")
    assert templates.overrides(store) == {"kuma": "{icon} {monitor} {state}"}
    templates.save(store, "kuma", templates.CATALOG["kuma"].default)
    assert templates.overrides(store) == {}
    templates.save(store, "kuma", "{monitor}")
    templates.reset(store, "kuma")
    assert templates.text_of(store, "kuma") == templates.CATALOG["kuma"].default


@pytest.mark.parametrize(("text", "error"), [
    ("", "cannot be empty"),
    ("{monitor} {nope}", "Unknown placeholder: {nope}."),
    ("<b>{monitor}", "<b> is never closed."),
    ("<b>{monitor}</i>", "</i> does not close an open <i>."),
    ('<a>{monitor}</a>', "<a> is not allowed"),
    ("x" * 2001, "under 2000 characters"),
])
def test_check_rejects_broken_templates(text, error):
    with pytest.raises(templates.TemplateError, match=error.replace("{", r"\{").replace(
            "}", r"\}").replace("(", r"\(").replace(")", r"\)").replace(".", r"\.")):
        templates.check("kuma", text)


def test_every_default_is_valid_and_every_line_has_a_message():
    for tid, t in templates.CATALOG.items():
        templates.check(tid, t.default)
        if t.parent:
            assert any(b.template == tid for b in templates.CATALOG[t.parent].blocks.values())


# --- senders on the NAS --------------------------------------------------------------


def test_backup_figures_use_the_template_and_bad_figures_fall_back(store):
    sent = formats.backup(store, {"ok": True, "minutes": 23, "volumes": [
        {"name": "volume1", "label": "docker", "ok": True},
        {"name": "volume3", "label": "files", "ok": True}]})
    # The same text backup.sh used to send.
    assert sent.html == core.format_html("ok", "NAS backup OK",
                                         "✅ volume1 (docker)\n✅ volume3 (files)\n⏱ 23 min")
    assert formats.backup(store, {"ok": True}) is None


WATCHTOWER_BODY = "✅ sonarr (lscr.io/linuxserver/sonarr:latest)\n❌ bazarr: pull access denied"


def test_watchtower_report_is_read_back_or_left_alone(store):
    title = "🔄 Watchtower: 24 scanned, 1 updated, 1 failed"
    sent = formats.watchtower(store, "info", title, WATCHTOWER_BODY)
    assert sent.html == core.format_html("info", title, WATCHTOWER_BODY)

    templates.save(store, "watchtower_updated", "⬆️ {name}")
    assert "⬆️ sonarr" in formats.watchtower(store, "info", title, WATCHTOWER_BODY).html
    assert formats.watchtower(store, "info", title, "something else entirely") is None
    assert formats.watchtower(store, "info", "Watchtower started", "") is None


def test_notify_endpoint_words_backup_with_the_saved_template(client, store):
    templates.save(store, "backup_ok", "{icon} Backup done in {minutes} min")
    body = {"source": "backup", "category": "backup", "severity": "ok",
            "title": "NAS backup OK", "body": "old text",
            "data": {"ok": True, "minutes": 7, "volumes": []}}
    resp = client.post("/api/notify", json=body, headers=SAME_ORIGIN | {"X-Notify-Key": KEY})
    assert resp.status_code == 200
    assert resp.json()["title"] == "Backup done in 7 min"
    assert client.fake.sent == [("-1001", "✅ Backup done in 7 min")]

    # Without figures (an older backup.sh) the text goes out as sent.
    body.pop("data")
    client.post("/api/notify", json=body, headers=SAME_ORIGIN | {"X-Notify-Key": KEY})
    assert client.fake.sent[-1] == ("-1001", core.format_html("ok", "NAS backup OK", "old text"))


def test_kuma_webhook_uses_the_template(client, store):
    templates.save(store, "kuma", "{icon} {monitor}: {state}")
    payload = {"heartbeat": {"status": 0, "msg": "refused"}, "monitor": {"name": "Jellyfin"},
               "msg": ""}
    client.post("/api/notify/kuma", json=payload, headers=SAME_ORIGIN | {"X-Notify-Key": KEY})
    assert client.fake.sent == [("-1001", "❌ Jellyfin: is down")]


# --- the Settings API ------------------------------------------------------------------


def test_list_shows_text_placeholders_and_a_preview(client):
    items = {t["id"]: t for t in client.get("/api/alerts/templates").json()}
    assert set(items) == set(templates.CATALOG)
    disk = items["disk_space"]
    assert (disk["group"], disk["customised"], disk["category"]) == (
        "Alert rules", False, "Hub alert rules")
    assert {"name": "pool", "description": "Pool name", "block": False} in disk["placeholders"]
    assert disk["preview"].startswith("⚠️ <b>volume2 is 92% full</b>")
    holding = items["portfolio_holding"]
    assert holding["parent"] == "portfolio_report"
    assert "<b>VWRL</b>" in holding["preview"]  # shown inside the whole report


def test_save_reset_and_validation_errors(client):
    saved = client.put("/api/alerts/templates/kuma", json={"text": "{icon} {monitor}"},
                       headers=SAME_ORIGIN)
    assert (saved.json()["customised"], saved.json()["preview"]) == (True, "❌ Jellyfin")

    bad = client.put("/api/alerts/templates/kuma", json={"text": "{nope}"}, headers=SAME_ORIGIN)
    assert bad.status_code == 422 and "Unknown placeholder" in bad.json()["detail"]

    reset = client.delete("/api/alerts/templates/kuma", headers=SAME_ORIGIN)
    assert reset.json()["customised"] is False
    assert client.put("/api/alerts/templates/nope", json={"text": "x"},
                      headers=SAME_ORIGIN).status_code == 404
    # Writes need the same-origin JSON guard.
    assert client.put("/api/alerts/templates/kuma", json={"text": "{monitor}"},
                      headers={"Origin": "http://evil.example"}).status_code == 403


def test_preview_reports_problems_instead_of_failing(client):
    ok = client.post("/api/alerts/templates/portfolio_index/preview",
                     json={"text": "{label}: {pct}"}, headers=SAME_ORIGIN).json()
    assert ok["error"] is None and "S&amp;P 500: +0,52%  AEX: +0,31%" in ok["html"]
    bad = client.post("/api/alerts/templates/kuma/preview", json={"text": "<b>{monitor}"},
                      headers=SAME_ORIGIN).json()
    assert bad["error"] == "<b> is never closed."


def test_send_test_goes_to_the_messages_chat_even_in_quiet_hours(client, store):
    core.put_setting(store, "quiet", {"enabled": True, "start": "00:00", "end": "23:59"})
    resp = client.post("/api/alerts/templates/portfolio_holding/test",
                       json={"text": "{symbol} {pct}"}, headers=SAME_ORIGIN)
    assert resp.status_code == 200
    assert (resp.json()["source"], resp.json()["status"]) == ("hub.test", "sent")
    assert resp.json()["title"].startswith("Test: ")
    ((chat, text),) = client.fake.sent
    assert chat == "-1002" and "VWRL +1,12%" in text
    assert client.post("/api/alerts/templates/kuma/test", json={"text": "{x}"},
                       headers=SAME_ORIGIN).status_code == 422


def test_saved_templates_reach_rule_alerts_and_resolved(store):
    from datetime import UTC, datetime, timedelta

    from app.alerts import rules

    rules.ensure_tables(store)
    templates.save(store, "smart_failing", "{icon} 💀 {disk}")
    templates.save(store, "resolved", "{icon} fixed: {title} ({duration})")
    fake = FakeTelegram()
    now = datetime(2026, 10, 4, 12, 0, tzinfo=UTC)
    problem = rules.Problem("smart:sdb", "smart", "error", "smart_failing", {"disk": "sdb"})
    asyncio.run(rules.apply(store, CFG, {"smart": [problem]}, now, fake))
    asyncio.run(rules.apply(store, CFG, {"smart": []}, now + timedelta(minutes=5), fake))
    assert [t for _, t in fake.sent] == ["❌ 💀 sdb", "✅ fixed: 💀 sdb (5 min)"]
    # The built-in wording is still what the rule reports.
    assert problem.title == "Disk sdb is failing (SMART)"
