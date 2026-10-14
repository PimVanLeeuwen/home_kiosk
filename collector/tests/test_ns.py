from __future__ import annotations

import asyncio
import copy
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx
import pytest

from app.sources import ns

FIXTURES = Path(__file__).parent / "fixtures"
TRIPS = json.loads((FIXTURES / "ns_trips.json").read_text())
JOURNEY = json.loads((FIXTURES / "ns_journey.json").read_text())
DISRUPTIONS = json.loads((FIXTURES / "ns_disruptions.json").read_text())

AMS = ZoneInfo("Europe/Amsterdam")
DEPARTURE = datetime(2026, 10, 14, 7, 16, tzinfo=AMS)  # a Wednesday, as in the fixtures
CFG = {"timezone": "Europe/Amsterdam",
       "train": {"api_key": "k", "from": "LEDN", "to": "RTD", "departure": "07:16",
                 "watch_from": "06:00", "evening": ["20:00", "22:00"]}}

VOORSCHOTEN, SCHIEDAM, LEIDEN = "8400659", "8400553", "8400390"


def local(*args: int) -> datetime:
    return datetime(*args, tzinfo=AMS).astimezone(UTC)


def the_716(trips: dict) -> dict:
    return next(t for t in trips["trips"] if t["transfers"] == 0
                and t["legs"][0]["origin"]["plannedDateTime"].endswith("07:16:00+0200"))


def shifted(trip: dict, minutes: int, actual: int = 0) -> dict:
    """A copy of a trip planned `minutes` later, running `actual` minutes late."""
    out = copy.deepcopy(trip)

    def move(value: str | None, by: int) -> str | None:
        if not value:
            return value
        moved = datetime.fromisoformat(value) + timedelta(minutes=by)
        return moved.strftime("%Y-%m-%dT%H:%M:%S%z")

    for leg in out["legs"]:
        for point in (leg["origin"], leg["destination"]):
            point["plannedDateTime"] = move(point["plannedDateTime"], minutes)
            point["actualDateTime"] = move(point["plannedDateTime"], actual)
        for stop in leg["stops"]:
            for key in ("plannedDepartureDateTime", "plannedArrivalDateTime"):
                stop[key] = move(stop.get(key), minutes)
            for key, planned in (("actualDepartureDateTime", "plannedDepartureDateTime"),
                                 ("actualArrivalDateTime", "plannedArrivalDateTime")):
                if stop.get(planned):
                    stop[key] = move(stop[planned], actual)
    return out


def with_trips(*trips: dict) -> dict:
    return {"trips": list(trips)}


# --- parsing ------------------------------------------------------------------


def test_finds_the_direct_716_with_its_track_and_stops():
    run = ns.find_train(TRIPS["trips"], DEPARTURE)

    assert run.name == "IC 3522"
    assert run.status == "on_time" and run.delay_minutes == 0
    assert (run.planned_track, run.actual_track) == ("6", "6")
    assert [s.name for s in run.stops] == [
        "Leiden Centraal", "Den Haag HS", "Delft", "Rotterdam Centraal"]
    assert run.stops[-1].planned == datetime(2026, 10, 14, 8, 28, tzinfo=AMS)


def test_ignores_trips_with_a_transfer():
    # The 07:06 has one transfer; it is never "the train".
    assert ns.find_train(TRIPS["trips"], datetime(2026, 10, 14, 7, 6, tzinfo=AMS)) is None


def test_a_late_train_says_by_how_much():
    late = shifted(the_716(TRIPS), 0, actual=6)

    run = ns.find_train([late], DEPARTURE)

    assert run.status == "late" and run.delay_minutes == 6
    assert run.actual_departure == datetime(2026, 10, 14, 7, 22, tzinfo=AMS)


def test_a_cancelled_train_and_the_next_direct_one():
    cancelled = copy.deepcopy(the_716(TRIPS))
    cancelled["legs"][0]["cancelled"] = True
    later = shifted(the_716(TRIPS), 30)

    trips = [cancelled, later]

    assert ns.find_train(trips, DEPARTURE).status == "cancelled"
    nxt = ns.next_direct(trips, DEPARTURE)
    assert nxt.planned_departure == datetime(2026, 10, 14, 7, 46, tzinfo=AMS)


def test_route_lists_every_station_from_leiden_to_rotterdam_passing_ones_too():
    codes = ns.parse_route(JOURNEY, "Leiden Centraal", "Rotterdam Centraal")

    assert len(codes) == 12
    assert codes[0] == "8400390" and codes[-1] == "8400530"
    assert VOORSCHOTEN in codes and SCHIEDAM in codes
    assert "8400603" not in codes  # Sassenheim, before Leiden
    assert "8400529" not in codes  # Rotterdam Blaak, after Rotterdam Centraal


ROUTE = ns.parse_route(JOURNEY, "Leiden Centraal", "Rotterdam Centraal")


def works(stations: list[str], start: str, end: str, active: bool = True) -> dict:
    return {"id": "w1", "type": "MAINTENANCE", "isActive": active,
            "title": "Leiden - Rotterdam.",
            "expectedDuration": {"description": "Dit duurt tot ongeveer 10:00 uur."},
            "timespans": [{"start": start, "end": end,
                           "situation": {"label": "Door werkzaamheden rijden er minder treinen."}}],
            "publicationSections": [{"section": {"stations": [{"uicCode": c} for c in stations]},
                                     "consequence": {"description": "minder treinen"}}]}


def test_only_disruptions_covering_two_route_stations_count():
    # The real answer: Utrecht - Leiden shares only Leiden Centraal with the route.
    assert ns.route_disruptions(DISRUPTIONS, ROUTE) == []

    found = ns.route_disruptions(
        [works([LEIDEN, SCHIEDAM], "2026-10-14T05:00:00+0200", "2026-10-14T10:00:00+0200")], ROUTE)

    assert [(d.title, d.text, d.until) for d in found] == [
        ("Leiden - Rotterdam.", "Door werkzaamheden rijden er minder treinen.",
         "Dit duurt tot ongeveer 10:00 uur.")]


def test_the_evening_check_keeps_planned_works_that_cover_the_departure():
    planned = works([LEIDEN, SCHIEDAM], "2026-10-14T05:00:00+0200", "2026-10-14T10:00:00+0200",
                    active=False)
    afternoon = works([LEIDEN, SCHIEDAM], "2026-10-14T13:00:00+0200", "2026-10-14T16:00:00+0200",
                      active=False)

    assert len(ns.route_disruptions([planned, afternoon], ROUTE, at=DEPARTURE)) == 1
    # Without a moment only active ones count.
    assert ns.route_disruptions([planned], ROUTE) == []


# --- collect -----------------------------------------------------------------


class NS:
    """A fake NS API answering from the fixtures, counting the calls per path."""

    def __init__(self, trips: dict = TRIPS, fail: bool = False):
        self.trips, self.fail, self.calls = trips, fail, []

    def transport(self) -> httpx.MockTransport:
        def handler(request: httpx.Request) -> httpx.Response:
            path = request.url.path.removeprefix("/reisinformatie-api/api")
            self.calls.append(path)
            assert request.headers["Ocp-Apim-Subscription-Key"] == "k"
            if self.fail:
                return httpx.Response(503)
            answer = {"/v3/trips": self.trips, "/v2/journey": JOURNEY,
                      "/v3/disruptions": DISRUPTIONS}[path]
            return httpx.Response(200, json=answer)

        return httpx.MockTransport(handler)


def run(store, now: datetime, api: NS) -> dict:
    train = asyncio.run(ns.collect(CFG, store, now=now, transport=api.transport()))
    payload = train.model_dump(mode="json")
    store.put_cache(ns.CACHE_KEY, payload)
    return payload


def test_weekends_and_early_mornings_make_no_calls(store):
    api = NS()

    saturday = run(store, local(2026, 10, 17, 7, 0), api)
    early = run(store, local(2026, 10, 14, 5, 30), api)

    assert api.calls == []
    assert (saturday["mode"], saturday["watching"]) == ("idle", False)
    assert early["mode"] == "idle"


def test_the_morning_follows_the_train_and_reads_the_route_once(store):
    api = NS()

    first = run(store, local(2026, 10, 14, 6, 30), api)
    run(store, local(2026, 10, 14, 6, 32), api)

    assert (first["mode"], first["watching"], first["departed"]) == ("morning", True, False)
    assert first["date"] == "2026-10-14" and first["departure"] == "07:16"
    assert first["route"] == "Leiden Centraal to Rotterdam Centraal"
    assert first["train"]["name"] == "IC 3522" and len(first["route_codes"]) == 12
    assert api.calls.count("/v2/journey") == 1
    assert api.calls.count("/v3/trips") == 2


def test_once_it_has_left_the_card_hides_and_nas_is_not_asked_again(store):
    api = NS()

    gone = run(store, local(2026, 10, 14, 7, 17), api)
    calls = len(api.calls)
    run(store, local(2026, 10, 14, 7, 19), api)

    assert (gone["departed"], gone["watching"]) == (True, False)
    assert len(api.calls) == calls


def test_a_train_the_planner_drops_is_not_found(store):
    run(store, local(2026, 10, 14, 6, 30), NS())
    others = with_trips(*[t for t in TRIPS["trips"] if t is not the_716(TRIPS)])

    later = run(store, local(2026, 10, 14, 6, 40), NS(others))

    assert later["train"]["status"] == "not_found" and later["watching"] is True


def test_the_evening_before_checks_tomorrows_train_at_each_check_time(store):
    api = NS()

    at_20 = run(store, local(2026, 10, 13, 20, 1), api)  # Tuesday, for Wednesday
    run(store, local(2026, 10, 13, 21, 0), api)
    calls = api.calls.count("/v3/trips")
    run(store, local(2026, 10, 13, 22, 1), api)

    assert (at_20["mode"], at_20["date"]) == ("evening", "2026-10-14")
    assert at_20["watching"] is False  # runs as planned: nothing to show
    assert calls == 1 and api.calls.count("/v3/trips") == 2


def test_the_evening_shows_a_cancelled_train_tomorrow(store):
    cancelled = copy.deepcopy(the_716(TRIPS))
    cancelled["legs"][0]["cancelled"] = True

    payload = run(store, local(2026, 10, 13, 20, 1),
                  NS(with_trips(cancelled, shifted(the_716(TRIPS), 30))))

    assert payload["watching"] is True
    assert payload["train"]["status"] == "cancelled"
    assert payload["next_direct"]["planned_departure"].startswith("2026-10-14T07:46")


def test_no_evening_check_before_a_weekend(store):
    api = NS()

    friday = run(store, local(2026, 10, 16, 20, 30), api)
    sunday = run(store, local(2026, 10, 18, 20, 30), api)

    assert friday["mode"] == "idle"
    assert (sunday["mode"], sunday["date"]) == ("evening", "2026-10-19")


def test_a_failing_ns_raises_so_the_last_answer_goes_stale(store):
    with pytest.raises(httpx.HTTPStatusError):
        asyncio.run(ns.collect(CFG, store, now=local(2026, 10, 14, 6, 30),
                               transport=NS(fail=True).transport()))


def test_switched_off_without_a_key():
    assert ns.settings({"train": {"api_key": "", "from": "LEDN", "to": "RTD"}})["enabled"] is False
    assert ns.settings(CFG)["enabled"] is True
