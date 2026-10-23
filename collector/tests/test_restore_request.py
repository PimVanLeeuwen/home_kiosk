from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

from app import main, restore_request

NOW = datetime(2026, 10, 23, 12, 0, tzinfo=UTC)


def test_a_request_is_left_for_the_nas_and_shown(tmp_path):
    folder = tmp_path
    assert restore_request.state(folder) == {"state": "idle", "since": None}
    old = [{"started": (NOW - timedelta(days=14)).isoformat()}]
    assert restore_request.request(folder, old, NOW) == {"state": "requested",
                                                         "since": NOW.isoformat()}
    assert (folder / restore_request.REQUEST).read_text() == NOW.isoformat()
    # The NAS takes it: renamed while it runs.
    (folder / restore_request.REQUEST).rename(folder / restore_request.RUNNING)
    assert restore_request.state(folder)["state"] == "running"


def test_not_twice_and_not_within_the_hour(tmp_path):
    restore_request.request(tmp_path, [], NOW)
    try:
        restore_request.request(tmp_path, [], NOW)
        raise AssertionError("asked twice")
    except restore_request.NotNow:
        pass
    (tmp_path / restore_request.REQUEST).unlink()
    recent = [{"started": (NOW - timedelta(minutes=20)).isoformat()}]
    try:
        restore_request.request(tmp_path, recent, NOW)
        raise AssertionError("asked within the hour")
    except restore_request.NotNow as exc:
        assert "less than an hour" in str(exc)


def test_the_routes_need_the_same_origin(store):
    main.app.state.store = store
    browser = TestClient(main.app, headers={"origin": "http://testserver"})
    assert browser.get("/api/backups/restore-check").json()["state"] == "idle"
    asked = browser.post("/api/backups/restore-check", json={})
    assert asked.status_code == 202 and asked.json()["state"] == "requested"
    assert browser.post("/api/backups/restore-check", json={}).status_code == 409
    foreign = TestClient(main.app, headers={"origin": "https://evil.example"})
    assert foreign.post("/api/backups/restore-check", json={}).status_code == 403
