"""The town's streets under the runs (plan.md M28, step 5). A made-up town in the North Sea."""

from __future__ import annotations

import asyncio
from datetime import UTC, date, datetime
from urllib.parse import parse_qs
from zoneinfo import ZoneInfo

import httpx
import pytest
from fastapi.testclient import TestClient

from app import desk_running, main, paint_run, paint_streets
from app.sources import runs, streets
from tests.test_running import run_on

ZONE = ZoneInfo("Europe/Amsterdam")
OVERPASS = {"elements": [
    {"type": "way", "tags": {"highway": "residential", "name": "Somewhere"},
     "geometry": [{"lat": 52.5, "lon": 3.49}, {"lat": 52.51, "lon": 3.5}]},
    {"type": "way", "tags": {"highway": "primary"},
     "geometry": [{"lat": 52.49, "lon": 3.48}, {"lat": 52.52, "lon": 3.51}]},
    {"type": "way", "tags": {"highway": "footway"},
     "geometry": [{"lat": 52.5, "lon": 3.5}, {"lat": 52.5005, "lon": 3.5005}]},
    {"type": "way", "tags": {"waterway": "river"},
     "geometry": [{"lat": 52.495, "lon": 3.47}, {"lat": 52.497, "lon": 3.53}]},
    {"type": "way", "tags": {"leisure": "park"}, "geometry": [
        {"lat": 52.51, "lon": 3.51}, {"lat": 52.512, "lon": 3.51}, {"lat": 52.512, "lon": 3.513},
        {"lat": 52.51, "lon": 3.51}]},
    {"type": "way", "tags": {"building": "yes"},
     "geometry": [{"lat": 52.5, "lon": 3.5}, {"lat": 52.5001, "lon": 3.5001}]},
]}


def test_the_box_round_the_runs():
    s, w, n, e = streets.box_round([[52.5, 3.5], [52.52, 3.53]])
    assert s < 52.5 and n > 52.52 and w < 3.5 and e > 3.53  # with a margin
    s, w, n, e = streets.box_round([[52.5, 3.5]])
    assert n - s == pytest.approx(streets.MIN_SPAN, abs=1e-4)  # a single point: a small town
    s, w, n, e = streets.box_round([[52.0, 3.0], [53.0, 4.0]])
    assert n - s == pytest.approx(streets.MAX_SPAN, abs=1e-4)  # never more than a city
    assert streets.box_round([]) is None


def test_fetched_once_and_kept_as_shapes_without_names(store):
    sent = []

    def handler(request):
        sent.append(parse_qs(request.content.decode())["data"][0])
        return httpx.Response(200, json=OVERPASS)

    status = asyncio.run(streets.fetch(store, [[52.5, 3.5], [52.51, 3.51]],
                                       transport=httpx.MockTransport(handler)))
    assert status["counts"] == {"major": 1, "minor": 1, "path": 1, "water": 1, "park": 1}
    assert "out geom" in sent[0] and "52.49" in sent[0]
    assert "Somewhere" not in str(streets.kept(store))
    with pytest.raises(ValueError):
        asyncio.run(streets.fetch(store, []))


@pytest.fixture
def client(store):
    main.app.state.store = store
    main.app.state.config = {"timezone": "Europe/Amsterdam"}
    return TestClient(main.app, headers={"origin": "http://testserver"})


def test_the_settings_routes(client, store, monkeypatch):
    assert client.get("/api/runs/streets").json() == {"fetched_at": None, "counts": {}}
    assert client.post("/api/runs/streets", json={}).status_code == 409  # no runs yet
    runs.receive(store, {"data": {"workouts": [run_on(date(2026, 10, 27), "r1")]}})

    async def fails(*args, **kwargs):
        raise httpx.ConnectError("no")

    monkeypatch.setattr(streets, "fetch", fails)
    assert client.post("/api/runs/streets", json={}).status_code == 502
    foreign = client.post("/api/runs/streets", json={}, headers={"origin": "https://evil.example"})
    assert foreign.status_code == 403


def test_your_streets_on_the_panel_with_todays_run_and_on_the_page(client, store):
    now = datetime(2026, 10, 27, 18, tzinfo=UTC)
    assert not desk_running.streets_screen(store, ZONE, now)["present"]
    runs.receive(store, {"data": {"workouts": [run_on(date(2026, 10, 20), "r0"),
                                               run_on(date(2026, 10, 27), "r1")]}})
    asyncio.run(streets.fetch(store, [[52.5, 3.5]], transport=httpx.MockTransport(
        lambda r: httpx.Response(200, json=OVERPASS))))

    screen = desk_running.streets_screen(store, ZONE, now)
    texts = [label["text"] for label in screen["labels"]]
    assert screen["present"] and "YOUR STREETS · 2026" in texts and "2 RUNS · 10 KM" in texts
    assert screen["today_run"] == "r1" and len(screen["path"]) == desk_running.PATH_POINTS
    later = desk_running.streets_screen(store, ZONE, datetime(2026, 10, 29, 18, tzinfo=UTC))
    assert later["present"] and later["path"] == [] and later["today_run"] is None
    picture = paint_streets.paint_streets(paint_streets.inputs(screen, now), store)
    assert picture.size == (720, 720)
    run = desk_running.run_screen(store, ZONE, now)
    assert run["streets_at"] and paint_run.paint_run(paint_run.inputs(run, now), store)

    got = client.get("/api/runs/streets/picture")
    assert got.status_code == 200 and got.headers["content-type"] == "image/jpeg"
