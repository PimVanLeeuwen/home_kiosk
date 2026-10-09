from __future__ import annotations

from datetime import UTC, datetime, timedelta

import httpx
import pytest
from fastapi.testclient import TestClient

from app import main
from app.alerts import rules
from app.sources import exposure

KEY = "notify-secret"
NOW = datetime(2026, 10, 9, 4, 30, tzinfo=UTC)


@pytest.fixture
def client(store):
    main.app.state.store = store
    main.app.state.config = {"telegram": {"notify_key": KEY}}
    return TestClient(main.app)


def scan(open_ports=(), error=None, at=NOW):
    return {"started": (at - timedelta(minutes=3)).isoformat(), "finished": at.isoformat(),
            "ports_checked": 65535, "open": list(open_ports), "error": error}


def test_the_target_and_the_result_need_the_notify_key(client):
    assert client.get("/api/exposure/target").status_code == 401
    assert client.post("/api/exposure/scan", json=scan()).status_code == 401
    assert client.get("/api/exposure/scan").status_code == 503  # nothing received yet


def test_the_target_is_the_home_ip_right_now(client, monkeypatch):
    async def fake_home_ip(_client: httpx.AsyncClient) -> str:
        return "203.0.113.7"

    monkeypatch.setattr(exposure, "home_ip", fake_home_ip)

    resp = client.get("/api/exposure/target", headers={"X-Notify-Key": KEY})
    assert resp.json() == {"ip": "203.0.113.7"}


def test_results_are_kept_newest_first_and_checked(client):
    headers = {"X-Notify-Key": KEY}
    client.post("/api/exposure/scan", json=scan(at=NOW - timedelta(days=1)), headers=headers)

    resp = client.post("/api/exposure/scan", json=scan([443, 22, 22]), headers=headers)

    runs = resp.json()["runs"]
    assert [r["open"] for r in runs] == [[22, 443], []]
    assert client.get("/api/exposure/scan").json()["runs"][0]["open"] == [22, 443]
    bad = client.post("/api/exposure/scan", json=scan([70000]), headers=headers)
    assert bad.status_code == 422


def test_an_open_port_is_an_error_and_a_missing_scan_a_warning():
    settings = {"hours": 48}

    def judge(*runs, now=NOW):
        return rules.port_scan({"runs": list(runs)}, settings, now)

    assert judge(scan()) == []
    assert rules.port_scan(None, settings, NOW) == []  # never ran: quiet

    (port,) = judge(scan([32400]))
    assert (port.key, port.severity, port.title) == (
        "port_scan:32400", "error", "Port 32400 is open on the home IP")

    late = judge(scan(), now=NOW + timedelta(hours=50))
    assert [(p.key, p.severity) for p in late] == [("port_scan:missing", "warning")]

    # A failed run does not count; the good one before it still decides the ports.
    failed = judge(scan(error="Home IP not found", at=NOW), scan([22], at=NOW - timedelta(days=3)))
    assert [p.key for p in failed] == ["port_scan:missing", "port_scan:22"]
    assert failed[0].body.endswith("Home IP not found")
