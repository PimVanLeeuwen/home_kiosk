from __future__ import annotations

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from app import desk_sites

ZONE = ZoneInfo("Europe/Amsterdam")
NOW = datetime(2026, 10, 21, 21, 46, tzinfo=UTC)


def site(name: str, **extra) -> dict:
    return {"id": 1, "name": name, "group": "Hubble", "up": True, "down_since": None,
            "ping_ms": 62, "uptime_pct": 100.0, "days": ["none"] * 22 + ["up"] * 8} | extra


def screen(store, *sites: dict, stale: bool = False):
    store.put_cache("sites", {"as_of": NOW.isoformat(), "stale": stale, "sites": list(sites)})
    return desk_sites.sites_screen(store, ZONE, NOW)


def test_a_tile_per_site_with_its_ping_and_days(store):
    s = screen(store, site("aoc"), site("harry", uptime_pct=99.81,
                                        days=["up"] * 9 + ["down"] + ["up"] * 12 + ["blip"]
                                        + ["up"] * 7))
    assert (s["kind"], s["present"], s["title"], s["status"], s["down"]) == (
        "sites", True, "MY SITES · 30 DAYS", "ALL UP", 0)
    assert s["sites"][0] == {"name": "aoc", "state": "up", "left": "62 ms", "right": "",
                             "worst": "up", "days": "n" * 22 + "u" * 8}
    harry = s["sites"][1]
    assert (harry["right"], harry["worst"], harry["days"][9], harry["days"][22]) == (
        "99.81%", "down", "d", "b")


def test_a_site_that_is_down_says_for_how_long(store):
    s = screen(store, site("aoc"), site("example.com", up=False,
                                        down_since="2026-10-21T21:42:00+00:00"))
    assert (s["status"], s["down"]) == ("1 DOWN", 1)
    assert (s["sites"][1]["state"], s["sites"][1]["left"]) == ("down", "down 4 min")


def test_down_for_hours_and_days():
    assert desk_sites._down_for("2026-10-21T18:40:00Z", NOW) == "down 3 h"
    assert desk_sites._down_for("2026-10-18T21:00:00Z", NOW) == "down 3 d"
    assert desk_sites._down_for(None, NOW) == "down"


def test_no_heartbeat_yet_is_unknown_without_a_ping(store):
    s = screen(store, site("meteor.cafe", up=None, ping_ms=None, uptime_pct=None))
    assert s["sites"][0] | {"days": ""} == {"name": "meteor.cafe", "state": "unknown",
                                           "left": "", "right": "", "worst": "up", "days": ""}


def test_stale_data_and_at_most_eight_tiles(store):
    s = screen(store, *[site(f"s{i}") for i in range(10)], stale=True)
    assert s["stale"] is True and len(s["sites"]) == 8


def test_nothing_read_yet(store):
    assert desk_sites.sites_screen(store, ZONE, NOW) == {
        "kind": "sites", "stale": False, "present": False}
