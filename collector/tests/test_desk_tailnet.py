from __future__ import annotations

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from app import desk_tailnet

ZONE = ZoneInfo("Europe/Amsterdam")
NOW = datetime(2026, 10, 22, 9, 30, tzinfo=UTC)


def device(name: str, os: str = "macOS", **extra) -> dict:
    return {"name": name, "dns_name": f"{name}.tail1234.ts.net", "os": os,
            "ipv4": "100.64.0.2", "ipv6": None, "online": True, "last_seen": None,
            "connection": "direct", "relay": "ams", "endpoint": None, "exit_node": False,
            "rx_bytes": 0, "tx_bytes": 0} | extra


NAS = device("nas", "linux", ipv4="100.70.0.10", connection=None)


def screen(store, *peers: dict, health: list[str] | None = None, stale: bool = False):
    store.put_cache("tailnet", {"as_of": NOW.isoformat(), "stale": stale, "name": "tail1234",
                                "self": NAS, "peers": list(peers), "health": health or []})
    return desk_tailnet.tailnet_screen(store, ZONE, NOW)


def test_every_device_round_the_nas_by_how_it_connects(store):
    s = screen(store, device("macbook"), device("phone", "iOS", connection="relay"),
               device("living-tv", "tvOS", connection="idle", exit_node=True),
               device("desk-pc", "windows", online=False, connection=None,
                      last_seen="2026-10-22T04:12:00+00:00"))
    assert (s["kind"], s["present"], s["title"], s["status"], s["warn"]) == (
        "tailnet", True, "TAILNET · TAIL1234", "4 OF 5 ONLINE", False)
    assert [(n["label"], n["kind"], n["exit"], n["seen"]) for n in s["nodes"]] == [
        ("Mac", "direct", False, ""), ("iP", "relay", False, ""), ("TV", "idle", True, ""),
        ("PC", "offline", False, "5 h ago")]
    assert [(n["x"], n["y"]) for n in s["nodes"]] == [(22, 20), (78, 20), (78, 76), (22, 76)]
    assert [(r["name"], r["ip"], r["via"]) for r in s["rows"]] == [
        ("nas", "100.70.0.10", "this NAS"), ("macbook", "100.64.0.2", "direct"),
        ("phone", "100.64.0.2", "relay ams"), ("living-tv", "100.64.0.2", "idle")]


def test_a_health_warning_turns_the_pill_and_the_nas_row(store):
    s = screen(store, device("macbook"), health=["DNS unreachable"])
    assert (s["status"], s["warn"], s["rows"][0]["via"]) == (
        "1 HEALTH ISSUE", True, "DNS unreachable")
    assert screen(store, health=["a", "b"])["status"] == "2 HEALTH ISSUES"


def test_an_ipad_is_a_tablet_and_at_most_eight_on_the_map(store):
    s = screen(store, device("pims-ipad", "iOS"), *[device(f"d{i}") for i in range(10)],
               stale=True)
    assert s["nodes"][0]["label"] == "iPd" and len(s["nodes"]) == 8 and s["stale"] is True
    assert len(s["rows"]) == 1 + desk_tailnet.MAX_ROWS


def test_seen_reads_well():
    assert desk_tailnet._seen("2026-10-22T09:18:00+00:00", NOW) == "12 min ago"
    assert desk_tailnet._seen("2026-10-20T09:00:00+00:00", NOW) == "2 days ago"
    assert desk_tailnet._seen(None, NOW) == ""


def test_nothing_read_yet(store):
    assert desk_tailnet.tailnet_screen(store, ZONE, NOW) == {
        "kind": "tailnet", "stale": False, "present": False}
