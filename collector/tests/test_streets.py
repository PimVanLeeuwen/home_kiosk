"""The town's streets under the runs (plan.md M28, step 5). A made-up town in the North Sea."""

from __future__ import annotations

import asyncio
from datetime import UTC, date, datetime
from io import BytesIO
from urllib.parse import parse_qs
from zoneinfo import ZoneInfo

import httpx
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app import desk_running, main, paint_run, paint_streets, running
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


def away(day: date, wid: str, north: float = 0.8) -> dict:
    """A run in another made-up town, about 90 km north of home."""
    run = run_on(day, wid)
    run["route"] = [p | {"latitude": p["latitude"] + north} for p in run["route"]]
    return run


def keep(store, *workouts):
    runs.receive(store, {"data": {"workouts": list(workouts)}})
    return runs.routes(store, streets.EVER)


def answer(sent=None):
    def handler(request):
        if sent is not None:
            sent.append(parse_qs(request.content.decode())["data"][0])
        return httpx.Response(200, json=OVERPASS)
    return httpx.MockTransport(handler)


def test_runs_are_grouped_by_area_with_home_where_most_are(store):
    routes = keep(store, away(date(2026, 10, 1), "a1"), run_on(date(2026, 10, 2), "h1"),
                  run_on(date(2026, 10, 3), "h2"))
    home, other = streets.group(routes)
    assert home["runs"] == ["h1", "h2"] and other["runs"] == ["a1"]
    areas = streets.status(store, routes)["areas"]
    assert [a["home"] for a in areas] == [True, False] and areas[1]["runs"] == 1
    assert areas[1]["where"] == "about 90 km north" and areas[1]["fetched_at"] is None


def test_fetched_per_area_and_kept_as_shapes_without_names(store):
    routes = keep(store, away(date(2026, 10, 1), "a1"), run_on(date(2026, 10, 2), "h1"),
                  run_on(date(2026, 10, 3), "h2"))
    home, other = streets.status(store, routes)["areas"]
    sent: list[str] = []
    status = asyncio.run(streets.fetch(store, routes, home["key"], transport=answer(sent)))
    got = status["areas"][0]
    assert got["counts"] == {"major": 1, "minor": 1, "path": 1, "water": 1, "park": 1}
    assert status["areas"][1]["fetched_at"] is None  # the other town is only fetched on request
    area = sent[0].split("way[highway](")[1].split(")")[0]
    s, w, n, e = (float(v) for v in area.split(","))
    assert s < 52.5 < n < 53.0 and w < 3.5 < e  # home's box only, not the town up north
    assert "Somewhere" not in str(streets.kept_for(store, [52.52, 3.5]))
    assert streets.kept_for(store, [53.32, 3.5]) is None

    asyncio.run(streets.fetch(store, routes, other["key"], transport=answer()))
    asyncio.run(streets.fetch(store, routes, home["key"], transport=answer()))  # again: replaced
    assert all(a["fetched_at"] for a in streets.status(store, routes)["areas"])
    with store.connect() as conn:
        assert conn.execute("SELECT COUNT(*) FROM street_area").fetchone()[0] == 2
    with pytest.raises(LookupError):
        asyncio.run(streets.fetch(store, routes, "40.0,10.0"))


def test_streets_fetched_before_areas_are_kept(store):
    with store.connect() as conn:
        conn.execute("CREATE TABLE street_map (id INTEGER PRIMARY KEY, fetched_at TEXT, box TEXT,"
                     " shapes TEXT)")
        conn.execute("INSERT INTO street_map VALUES (1, '2026-10-26T15:00:00+00:00', "
                     "'[52.4, 3.4, 52.6, 3.6]', '{\"minor\": [[[52.5, 3.5], [52.51, 3.5]]]}')")
    routes = keep(store, run_on(date(2026, 10, 2), "h1"))
    assert streets.status(store, routes)["areas"][0]["counts"] == {"minor": 1}
    with store.connect() as conn:
        assert not conn.execute("SELECT 1 FROM sqlite_master WHERE name = 'street_map'").fetchone()


@pytest.fixture
def client(store):
    main.app.state.store = store
    main.app.state.config = {"timezone": "Europe/Amsterdam"}
    return TestClient(main.app, headers={"origin": "http://testserver"})


def test_the_settings_routes(client, store, monkeypatch):
    assert client.get("/api/runs/streets").json() == {"areas": []}
    assert client.post("/api/runs/streets", json={"area": "52.5,3.5"}).status_code == 404
    assert client.post("/api/runs/streets", json={}).status_code == 422
    keep(store, run_on(date(2026, 10, 27), "r1"))
    key = client.get("/api/runs/streets").json()["areas"][0]["key"]

    async def fails(*args, **kwargs):
        raise httpx.ConnectError("no")

    monkeypatch.setattr(streets, "fetch", fails)
    assert client.post("/api/runs/streets", json={"area": key}).status_code == 502
    foreign = client.post("/api/runs/streets", json={"area": key},
                          headers={"origin": "https://evil.example"})
    assert foreign.status_code == 403


def test_your_streets_on_the_panel_with_todays_run_and_on_the_page(client, store):
    now = datetime(2026, 10, 27, 18, tzinfo=UTC)
    assert not desk_running.streets_screen(store, ZONE, now)["present"]
    routes = keep(store, run_on(date(2026, 10, 20), "r0"), run_on(date(2026, 10, 27), "r1"))
    asyncio.run(streets.fetch(store, routes, streets.status(store, routes)["areas"][0]["key"],
                              transport=answer()))

    screen = desk_running.streets_screen(store, ZONE, now)
    texts = [label["text"] for label in screen["labels"]]
    assert screen["present"] and "YOUR STREETS · 2026" in texts and "2 RUNS · 10 KM" in texts
    assert not any("ELSEWHERE" in t for t in texts)
    assert screen["today_run"] == "r1" and len(screen["path"]) == desk_running.PATH_POINTS
    later = desk_running.streets_screen(store, ZONE, datetime(2026, 10, 29, 18, tzinfo=UTC))
    assert later["present"] and later["path"] == [] and later["today_run"] is None
    picture = paint_streets.paint_streets(paint_streets.inputs(screen, now), store)
    assert picture.size == (720, 720)
    run = desk_running.run_screen(store, ZONE, now)
    assert run["streets_at"] and paint_run.paint_run(paint_run.inputs(run, now), store)

    got = client.get("/api/runs/streets/picture")
    assert got.status_code == 200 and got.headers["content-type"] == "image/jpeg"


def test_a_run_in_another_town_is_left_off_your_streets(store):
    now = datetime(2026, 10, 27, 18, tzinfo=UTC)
    routes = keep(store, run_on(date(2026, 10, 20), "r0"), run_on(date(2026, 10, 22), "r1"),
                  away(date(2026, 10, 27), "a1"))
    asyncio.run(streets.fetch(store, routes, streets.status(store, routes)["areas"][0]["key"],
                              transport=answer()))

    screen = desk_running.streets_screen(store, ZONE, now)
    texts = [label["text"] for label in screen["labels"]]
    assert "3 RUNS · 16 KM" in texts and "+1 RUN ELSEWHERE" in texts
    assert screen["count"] == 2 and screen["newest"] == "r1" and screen["today_run"] is None
    assert screen["elsewhere"] == 1 and screen["streets_at"]
    view = running.overview(store, ZONE, now)
    assert view["runs_elsewhere"] == 1 and view["streets_at"]
    run = desk_running.run_screen(store, ZONE, now)
    assert run["id"] == "a1" and run["streets_at"] is None  # its town was not fetched


def test_the_streets_under_the_last_runs_route_on_the_page(client, store):
    now = datetime(2026, 10, 27, 18, tzinfo=UTC)
    routes = keep(store, run_on(date(2026, 10, 20), "r0"), away(date(2026, 10, 27), "a1"))
    assert client.get("/api/runs/r0/streets").status_code == 404  # nothing fetched yet
    assert running.overview(store, ZONE, now)["last"]["streets_at"] is None
    home, other = streets.status(store, routes)["areas"]
    asyncio.run(streets.fetch(store, routes, other["key"], transport=answer()))

    assert running.overview(store, ZONE, now)["last"]["streets_at"]
    got = client.get("/api/runs/a1/streets")
    assert got.status_code == 200 and got.headers["content-type"] == "image/webp"
    picture = Image.open(BytesIO(got.content))
    assert picture.size == (1280, 760) and picture.mode == "RGBA"
    assert picture.getpixel((0, 0))[3] == 0  # transparent round the town
    assert client.get("/api/runs/r0/streets").status_code == 404  # home's are not in
    assert client.get("/api/runs/nope/streets").status_code == 404


def test_the_route_streets_frame_matches_the_cards_projection():
    """The card fits the route as web/src/lib/running.ts's `project` does: the route's corners
    land on the box less its pad, centred, at twice the size."""
    route = [[52.50, 3.50], [52.52, 3.53]]
    w, h, pad = paint_streets.ROUTE_ART
    s = paint_streets.ROUTE_ART_SCALE
    frame = paint_streets.Frame((52.50, 3.50, 52.52, 3.53), (pad * s, pad * s, (w - pad) * s,
                                                             (h - pad) * s), fit=True)
    (x0, y0), (x1, y1) = frame.xy(*route[0]), frame.xy(*route[1])
    assert y1 == pytest.approx(pad * s) and y0 == pytest.approx((h - pad) * s)  # height fills
    assert (x0 + x1) / 2 == pytest.approx(w * s / 2)
