from __future__ import annotations

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from app import desk_services

ZONE = ZoneInfo("Europe/Amsterdam")
NOW = datetime(2026, 10, 22, 12, 26, tzinfo=UTC)
KEYS = ["github", "cloudflare", "docker", "tailscale", "hetzner", "transip", "proton"]


def service(key: str, state: str = "ok", incidents: list | None = None) -> dict:
    return {"key": key, "name": key.title(), "url": "", "state": state,
            "incidents": incidents or [], "as_of": NOW.isoformat(), "stale": False}


def incident(impact: str, started: str, *steps: tuple[str, str], title: str = "Runs are delayed"):
    return {"title": title, "impact": impact, "status": steps[-1][0] if steps else "",
            "started_at": started, "updates": [{"at": at, "status": s, "text": ""}
                                               for s, at in steps]}


def screen(store, *services: dict, stale: bool = False):
    store.put_cache("outside_services", {"as_of": NOW.isoformat(), "stale": stale,
                                         "services": list(services)})
    return desk_services.services_screen(store, ZONE, NOW)


def test_all_well_lists_every_service_without_an_incident(store):
    s = screen(store, *[service(k) for k in KEYS])
    assert (s["kind"], s["present"], s["title"], s["status"], s["tone"]) == (
        "services", True, "SERVICES", "ALL OPERATIONAL", "ok")
    assert [x["key"] for x in s["services"]] == KEYS
    assert (s["incident"], s["others"]) == (None, "")


def test_an_incident_card_with_its_last_steps_newest_first(store):
    github = service("github", "degraded", [incident(
        "degraded", "2026-10-22T12:02:00Z",
        ("investigating", "2026-10-22T12:02:00Z"), ("identified", "2026-10-22T12:15:00Z"))])
    s = screen(store, github, *[service(k) for k in KEYS[1:]])
    assert (s["status"], s["tone"], s["others"]) == (
        "1 INCIDENT", "degraded", "the other 6 are operational")
    assert s["incident"] == {
        "key": "github", "name": "Github", "state": "degraded", "line": "Degraded · for 24 min",
        "title": "Runs are delayed",
        "steps": [{"status": "Identified", "time": "14:15"},
                  {"status": "Investigating", "time": "14:02"}]}


def test_the_worst_service_leads_and_the_rest_are_counted(store):
    s = screen(store, service("github", "maintenance",
                              [incident("maintenance", "2026-10-22T10:00:00Z")]),
               service("proton", "outage", [incident("outage", "2026-10-21T09:00:00Z")]),
               service("docker"))
    assert (s["status"], s["tone"], s["incident"]["key"]) == ("2 INCIDENTS", "outage", "proton")
    assert s["incident"]["line"] == "Outage · for 27 h"
    assert s["others"] == "1 more not fully operational"


def test_maintenance_alone_says_so(store):
    s = screen(store, service("hetzner", "maintenance", [incident("maintenance", None)]),
               service("github"))
    assert (s["status"], s["incident"]["line"]) == ("MAINTENANCE", "Maintenance")


def test_an_unreadable_page_is_no_incident(store):
    s = screen(store, service("transip", "unknown"), service("github"), stale=True)
    assert (s["status"], s["stale"], s["services"][0]["state"]) == (
        "ALL OPERATIONAL", True, "unknown")


def test_nothing_read_yet(store):
    assert desk_services.services_screen(store, ZONE, NOW) == {
        "kind": "services", "stale": False, "present": False}
