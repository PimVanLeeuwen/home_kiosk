from __future__ import annotations

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from fastapi.testclient import TestClient

from app import desk, desk_alerts, desk_boards, main

ZONE = ZoneInfo("Europe/Amsterdam")
NOW = datetime(2026, 10, 22, 18, 0, tzinfo=UTC)  # Thursday 20:00 in Amsterdam
CFG = {"timezone": "Europe/Amsterdam"}
MAC = "e8:f6:0a:e4:42:b0"


def incident(store, key, severity="warning", opened="2026-10-22T07:12:00+00:00",
             resolved=None, title=None, body="Line one.\nLine two."):
    with store.connect() as conn:
        conn.execute(
            "INSERT INTO alert_incident (key, rule, severity, title, body, opened_at, "
            "last_seen_at, resolved_at) VALUES (?, 'rule', ?, ?, ?, ?, ?, ?)",
            (key, severity, title or key, body, opened, opened, resolved))


def screen(store):
    return desk_alerts.alerts_screen(store, ZONE, NOW)


def test_all_quiet_with_how_long_and_this_week(store):
    incident(store, "disk", opened="2026-10-20T08:00:00+00:00",
             resolved="2026-10-20T18:00:00+00:00")
    incident(store, "move", severity="info", opened="2026-10-21T08:00:00+00:00")
    s = screen(store)
    assert (s["kind"], s["present"], s["status"], s["tone"]) == ("alerts", True, "NONE OPEN", "ok")
    assert s["quiet"]["line"] == "Nothing has needed you for 2 days"
    days = s["quiet"]["days"]
    assert [d["letter"] for d in days] == list("MTWTFSS")
    assert [d["alert"] for d in days] == ["", "warning", "", "", "", "", ""]  # info is no alert
    assert [d["today"] for d in days].index(True) == 3 and days[4]["future"] is True


def test_nothing_ever_needed_you(store):
    assert screen(store)["quiet"]["line"] == "Nothing has needed you lately"


def test_the_worst_open_alert_large_and_the_others_below(store):
    incident(store, "full", title="volume2 is 88% full", opened="2026-10-20T07:12:00+00:00")
    incident(store, "backup", severity="error", title="Backup failed: Files",
             opened="2026-10-22T01:41:00+00:00")
    incident(store, "move", severity="info")
    s = screen(store)
    assert (s["status"], s["tone"]) == ("2 OPEN", "error")
    assert s["hero"] == {"severity": "ERROR", "title": "Backup failed: Files",
                         "body": "Line one. Line two.", "line": "Open 16 hours · since 03:41"}
    assert s["others"] == [{"severity": "warning", "title": "volume2 is 88% full"}]
    assert "quiet" not in s


def test_an_open_error_takes_over_every_panel(store):
    incident(store, "backup", severity="error", title="Backup failed: Files",
             opened="2026-10-21T01:41:00+00:00", body="rclone stopped with exit code 1.")
    for name in ("now", "home", "house"):
        assert desk.answer(CFG, store, name, NOW)["takeover"] == {
            "key": "backup", "title": "Backup failed: Files",
            "body": "rclone stopped with exit code 1.", "since": "Wed 03:41"}
    assert desk.answer(CFG, store, None, NOW, board=MAC)["takeover"] is None


def test_warnings_never_take_over_and_a_long_body_is_cut(store):
    incident(store, "full")
    assert desk_alerts.takeover(store, ZONE, NOW) is None
    incident(store, "smart", severity="error", body="x " * 300)
    body = desk_alerts.takeover(store, ZONE, NOW)["body"]
    assert len(body) == desk_alerts.MAX_BODY and body.endswith("...")


def keyed_client(store) -> TestClient:
    main.app.state.store = store
    main.app.state.config = CFG
    desk_boards.ensure_tables(store)
    browser = TestClient(main.app, headers={"origin": "http://testserver"})
    browser.get(f"/api/desk/board/{MAC}")
    browser.put(f"/api/settings/desk-boards/{MAC}", json={"panel": "house"})
    key = browser.get(f"/api/desk/board/{MAC}").json()["key"]
    return TestClient(main.app, headers={"authorization": f"Bearer {key}"})


def test_dismissed_on_one_panel_until_it_opens_again(store):
    client = keyed_client(store)
    incident(store, "backup", severity="error")
    assert client.get(f"/api/desk/board/{MAC}").json()["takeover"]["key"] == "backup"

    assert client.post("/api/desk/alerts/dismiss", json={"key": "backup"}).json() == {"ok": True}
    assert client.get(f"/api/desk/board/{MAC}").json()["takeover"] is None
    assert desk.answer(CFG, store, "now")["takeover"] is None  # the other panels too
    assert screen(store)["hero"]["severity"] == "ERROR"  # still on the Alerts screen

    # Resolved, then failing again: a new takeover.
    with store.connect() as conn:
        conn.execute("UPDATE alert_incident SET resolved_at = ? WHERE key = 'backup'",
                     (NOW.isoformat(),))
    assert client.post("/api/desk/alerts/dismiss", json={"key": "backup"}).status_code == 404
    with store.connect() as conn:
        conn.execute("UPDATE alert_incident SET resolved_at = NULL, dismissed_at = NULL")
    assert desk_alerts.takeover(store, ZONE, NOW)["key"] == "backup"


def test_dismissing_needs_the_boards_key(store):
    keyed_client(store)
    incident(store, "backup", severity="error")
    assert TestClient(main.app).post("/api/desk/alerts/dismiss",
                                     json={"key": "backup"}).status_code == 401


def test_an_older_table_gets_the_dismissed_column(tmp_path):
    from app.alerts import rules
    from app.store import Store

    store = Store(tmp_path / "old.db")
    with store.connect() as conn:
        conn.execute("CREATE TABLE alert_incident (key TEXT PRIMARY KEY, rule TEXT NOT NULL, "
                     "severity TEXT NOT NULL, title TEXT NOT NULL, body TEXT NOT NULL DEFAULT '', "
                     "opened_at TEXT NOT NULL, last_seen_at TEXT NOT NULL, resolved_at TEXT)")
    rules.ensure_tables(store)
    with store.connect() as conn:
        columns = {r["name"] for r in conn.execute("PRAGMA table_info(alert_incident)")}
    assert "dismissed_at" in columns
