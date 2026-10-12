from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime

import httpx
import pytest

from app.sources import outside_services as outside

NOW = datetime(2026, 10, 12, 9, 0, tzinfo=UTC)

SUMMARY = {
    "components": [
        {"id": "dns", "name": "Authoritative DNS", "status": "operational"},
        {"id": "tun", "name": "Tunnel", "status": "operational"},
        {"id": "cn", "name": "China Network", "status": "major_outage"},
        {"id": "eu", "name": "Europe", "status": "degraded_performance", "group": True,
         "components": ["ams", "fra"]},
        {"id": "ams", "name": "Amsterdam, Netherlands - (AMS)", "status": "operational",
         "group_id": "eu"},
        {"id": "fra", "name": "Frankfurt, Germany - (FRA)", "status": "degraded_performance",
         "group_id": "eu"},
    ],
    "incidents": [
        {"id": "i1", "name": "Elevated Errors in China Network Colos", "status": "identified",
         "impact": "minor", "components": [{"id": "cn"}], "incident_updates": []},
    ],
    "scheduled_maintenances": [
        {"id": "m1", "name": "AMS maintenance", "status": "scheduled",
         "components": [{"id": "ams"}], "incident_updates": []},
    ],
}
WATCHED = ["Authoritative DNS", "Tunnel", "Amsterdam, Netherlands - (AMS)"]


def summary(**changes):
    return json.loads(json.dumps(SUMMARY)) | changes


def test_far_away_problems_do_not_count():
    state, incidents = outside.parse_statuspage(summary(), WATCHED, "https://cf")

    assert (state, incidents) == ("ok", [])


def test_an_incident_on_a_watched_component_counts_with_its_updates():
    data = summary(incidents=[{
        "id": "i2", "name": "Tunnel errors", "status": "monitoring", "impact": "major",
        "started_at": "2026-10-12T08:10:00.000Z", "shortlink": "https://stspg.io/x",
        "components": [{"id": "tun"}],
        "incident_updates": [
            {"status": "monitoring", "body": "A fix is out.", "created_at": "2026-10-12T08:40:00Z"},
            {"status": "investigating", "body": "We are  looking\ninto it.",
             "created_at": "2026-10-12T08:12:00Z"},
        ]}])

    state, [incident] = outside.parse_statuspage(data, WATCHED, "https://cf")

    assert state == "outage"
    assert (incident.title, incident.impact, incident.url) == (
        "Tunnel errors", "outage", "https://stspg.io/x")
    assert [(u.status, u.text) for u in incident.updates] == [
        ("investigating", "We are looking into it."), ("monitoring", "A fix is out.")]


def test_a_watched_group_covers_its_members():
    state, _ = outside.parse_statuspage(summary(), ["Europe"], "https://cf")

    assert state == "degraded"


def test_maintenance_counts_only_while_it_runs():
    data = summary()
    assert outside.parse_statuspage(data, WATCHED, "https://cf")[0] == "ok"

    data["scheduled_maintenances"][0]["status"] = "in_progress"
    state, [m] = outside.parse_statuspage(data, WATCHED, "https://cf")

    assert (state, m.impact, m.url) == ("maintenance", "maintenance", "https://cf/incidents/m1")


def test_a_renamed_component_is_an_error_not_all_clear():
    with pytest.raises(outside.PageError, match="watched components"):
        outside.parse_statuspage(summary(), ["Argo Tunnel"], "https://cf")


def hetzner_page(*incidents) -> str:
    props = {"props": {"pageProps": {
        "systems": [
            {"@id": "/systems/2", "titleEn": "Cloud", "parent": None},
            {"@id": "/systems/3", "titleEn": "Cloud Server", "parent": "/systems/2"},
            {"@id": "/systems/91", "titleEn": "Object Storage", "parent": "/systems/2"},
            {"@id": "/systems/11", "titleEn": "Storage Box", "parent": "/systems/10"},
            {"@id": "/systems/14", "titleEn": "FSN1", "parent": "/systems/13"},
            {"@id": "/systems/64", "titleEn": "FSN1-DC8", "parent": "/systems/14"},
        ],
        "incidents": {"topNotification": list(incidents), "incidentHistory": list(incidents)},
    }}}
    return ('<html><script id="__NEXT_DATA__" type="application/json">'
            f"{json.dumps(props)}</script></html>")


def hetzner_incident(system: str, title: str, kind: str = "outage", state: str = "identified",
                     start: str = "2026-10-12T07:00:00+00:00", end: str | None = None) -> dict:
    return {"id": hash(title), "uuid": "u-1", "system": system, "titleEn": title,
            "incidentType": kind, "incidentState": state, "startTime": start, "endTime": end,
            "incidentUpdates": [
                {"incidentState": "identified", "descriptionEn": "Seen.",
                 "createdAt": "2026-10-12T07:05:00+00:00", "visible": True},
                {"incidentState": "update", "descriptionEn": "Hidden.",
                 "createdAt": "2026-10-12T07:10:00+00:00", "visible": False}]}


HETZNER = (["Storage Box", "Cloud Server", "FSN1"], ["HEL1", "Ashburn"], "https://hz")


def test_hetzner_counts_watched_systems_and_their_locations_once():
    page = hetzner_page(hetzner_incident("/systems/64", "Power work in FSN1-DC8", "maintenance"),
                        hetzner_incident("/systems/11", "Storage Box slow", "warning"))

    state, incidents = outside.parse_hetzner(page, *HETZNER, NOW)

    assert state == "degraded"
    assert [(i.title, i.impact) for i in incidents] == [
        ("Power work in FSN1-DC8", "maintenance"), ("Storage Box slow", "degraded")]
    assert incidents[0].url == "https://hz/incident/u-1"
    assert [u.text for u in incidents[0].updates] == ["Seen."]


@pytest.mark.parametrize("incident", [
    hetzner_incident("/systems/91", "Object Storage in location FSN partially degraded"),
    hetzner_incident("/systems/3", "Cloud Servers in HEL1 unreachable"),
    hetzner_incident("/systems/3", "Cloud Servers down", state="resolved"),
    hetzner_incident("/systems/3", "Planned work", "maintenance", "planned",
                     start="2026-10-13T05:00:00+00:00"),
    hetzner_incident("/systems/3", "Done work", "maintenance", "planned",
                     start="2026-10-11T05:00:00+00:00", end="2026-10-11T07:00:00+00:00"),
    hetzner_incident("/systems/11", "Phishing emails", "other"),
])
def test_hetzner_skips_what_does_not_touch_the_house(incident):
    assert outside.parse_hetzner(hetzner_page(incident), *HETZNER, NOW) == ("ok", [])


def test_a_changed_hetzner_page_is_an_error():
    with pytest.raises(outside.PageError):
        outside.parse_hetzner("<html>new design</html>", *HETZNER, NOW)


def test_transnoc_is_fine_only_with_its_all_clear_sentence():
    ok = "<p>Al onze diensten\n zijn beschikbaar.</p>"
    assert outside.parse_transnoc(ok, "Al onze diensten zijn beschikbaar", "https://tn") == (
        "ok", [])

    state, [incident] = outside.parse_transnoc("<p>Storing DNS</p>",
                                               "Al onze diensten zijn beschikbaar", "https://tn")
    assert (state, incident.url) == ("degraded", "https://tn")


CFG = {"outside_services": [
    {"key": "cloudflare", "name": "Cloudflare", "url": "https://cf.test",
     "components": WATCHED},
    {"key": "transip", "name": "TransIP", "kind": "transnoc", "url": "https://tn.test"},
]}


def test_collects_every_page_and_a_failing_one_keeps_its_last_answer(store):
    def ok(request: httpx.Request) -> httpx.Response:
        if request.url.host == "cf.test":
            assert request.url.path == "/api/v2/summary.json"
            return httpx.Response(200, json=SUMMARY)
        return httpx.Response(200, text="Al onze diensten zijn beschikbaar.")

    first = asyncio.run(outside.collect(CFG, store, httpx.MockTransport(ok), NOW))
    assert [(s.key, s.state, s.stale) for s in first.services] == [
        ("cloudflare", "ok", False), ("transip", "ok", False)]
    store.put_cache(outside.CACHE_KEY, first.model_dump(mode="json"))

    def cloudflare_down(request: httpx.Request) -> httpx.Response:
        if request.url.host == "cf.test":
            return httpx.Response(503)
        return ok(request)

    later = datetime(2026, 10, 12, 9, 5, tzinfo=UTC)
    second = asyncio.run(outside.collect(CFG, store, httpx.MockTransport(cloudflare_down), later))
    cf, tn = second.services

    assert (cf.state, cf.stale, cf.as_of, cf.error) == (
        "ok", True, NOW, "the status page answered 503")
    assert (tn.stale, tn.as_of) == (False, later)


def test_a_page_never_reached_is_unknown(store):
    def down(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("no route")

    result = asyncio.run(outside.collect(CFG, store, httpx.MockTransport(down), NOW))

    assert [(s.state, s.stale, s.error) for s in result.services] == [
        ("unknown", True, "the status page could not be reached")] * 2


def test_no_services_means_no_job():
    assert outside.settings({}) == []
    assert [s["key"] for s in outside.settings(CFG)] == ["cloudflare", "transip"]
