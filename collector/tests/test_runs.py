"""Runs from Health Auto Export (plan.md M28). The route is made up: a line in the North Sea."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from app import main
from app.sources import runs

KEY = "test-runs-key"
CFG = {"running": {"key": KEY}}
START = datetime(2026, 10, 26, 7, 0, tzinfo=UTC)


def stamp(t: datetime) -> str:
    return t.astimezone().strftime("%Y-%m-%d %H:%M:%S %z")


def route(km: float = 5.2, seconds_per_km: int = 330):
    """Points every 10 s heading north at a steady pace."""
    metres_per_s = 1000 / seconds_per_km
    n = int(km * 1000 / metres_per_s / 10) + 1
    return [{"latitude": 52.5 + (i * 10 * metres_per_s) / 111_195, "longitude": 3.5,
             "altitude": 2.0, "timestamp": stamp(START + timedelta(seconds=i * 10)),
             "speed": metres_per_s, "course": 0, "horizontalAccuracy": 4} for i in range(n)]


def workout(wid="w1", name="Outdoor Run", miles=None, **over):
    distance = {"qty": round(miles, 3), "units": "mi"} if miles else {"qty": 5.2, "units": "km"}
    heart = [{"date": stamp(START + timedelta(minutes=m)), "Min": 120, "Avg": 140 + m,
              "Max": 160, "units": "bpm"} for m in range(3)]
    return {"id": wid, "name": name, "start": stamp(START),
            "end": stamp(START + timedelta(seconds=1716)), "duration": 1716, "isIndoor": False,
            "location": "Outdoor", "distance": distance,
            "elevationUp": {"qty": 39.4, "units": "ft"},
            "avgHeartRate": {"qty": 148.2, "units": "bpm"},
            "maxHeartRate": {"qty": 171, "units": "bpm"},
            "activeEnergyBurned": {"qty": 402.5, "units": "kcal"},
            "temperature": {"qty": 50, "units": "degF"}, "humidity": {"qty": 82, "units": "%"},
            "heartRateData": heart, "route": route(), **over}


@pytest.fixture
def client(store):
    main.app.state.store = store
    main.app.state.config = CFG
    return TestClient(main.app)


def post(client, body, key=KEY):
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    return client.post("/api/runs/health", content=json.dumps(body), headers=headers)


def test_only_runs_are_kept_once_each_with_metric_units(client, store):
    body = {"data": {"metrics": [], "workouts": [
        workout(), workout("w2", "Indoor Run", isIndoor=True, route=[]),
        {"id": "y1", "name": "Yoga", "start": stamp(START), "end": stamp(START), "duration": 60},
        {"id": "bad", "name": "Outdoor Run"},  # no start: unreadable, left out
    ]}}

    assert post(client, body).json() == {"kept": 2, "skipped": 1, "failed": 1}
    assert post(client, body).json()["kept"] == 2  # sent again: replaced, not doubled
    listed = client.get("/api/runs").json()["runs"]
    assert {r["id"] for r in listed} == {"w1", "w2"}

    run = client.get("/api/runs/w1").json()
    assert run["distance_m"] == 5200 and run["pace_s_per_km"] == 330
    assert run["elevation_up_m"] == 12.0 and run["temperature_c"] == 10.0 and not run["indoor"]
    assert run["heart"] == [[0, 140.0], [60, 141.0], [120, 142.0]]
    assert [s["km"] for s in run["splits"]] == [1, 2, 3, 4, 5, 6]
    assert all(abs(s["seconds"] - 330) <= 10 for s in run["splits"][:5])
    assert run["splits"][-1]["metres"] < 1000
    # The route with the pace since the point before; the first point has none.
    assert len(run["route"]) <= 400 and run["route"][0] == [52.5, 3.5, None]
    assert all(abs(p[2] - 330) <= 5 for p in run["route"][1:])
    assert run["bests"]["5k"] == pytest.approx(1650, abs=10) and run["bests"]["10k"] is None
    assert client.get("/api/runs/w2").json()["indoor"] is True
    assert client.get("/api/runs/nope").status_code == 404


def test_miles_and_feet_become_metres():
    run = runs.parse(workout(miles=3.231))
    assert run["distance_m"] == pytest.approx(5199.8, abs=0.5)


def test_the_phone_needs_the_key(client, store):
    assert post(client, {"data": {"workouts": [workout()]}}, key="wrong").status_code == 401
    no_key = client.post("/api/runs/health", content="{}",
                         headers={"Content-Type": "application/json"})
    assert no_key.status_code == 401
    assert client.post("/api/runs/health", content="not json",
                       headers={"Authorization": f"Bearer {KEY}"}).status_code == 400
    main.app.state.config = {}
    assert post(client, {"data": {"workouts": []}}).status_code == 503


def test_simplified_keeps_the_ends():
    points = [[float(i), 0.0, 0.0, i, 0.0] for i in range(1001)]
    short = runs.simplified(points, 5)
    assert short == [[0.0, 0.0], [250.0, 0.0], [500.0, 0.0], [750.0, 0.0], [1000.0, 0.0]]


def test_a_best_effort_is_the_fastest_stretch_inside_a_run():
    # 2 km at 6:00/km, then 5 km at 4:30/km, then 1 km easy again.
    points, t, lat = [], 0.0, 52.5
    for km, pace in ((2, 360), (5, 270), (1, 360)):
        for _ in range(km * 10):  # a point every 100 m
            points.append([lat, 3.5, 0.0, t, 0.0])
            lat += 100 / 111_195
            t += pace / 10
    points.append([lat, 3.5, 0.0, t, 0.0])
    assert runs.best_effort(points, 5000) == pytest.approx(1350, abs=15)
    assert runs.best_effort(points, 10000) is None
    assert runs.best_effort([], 5000) is None


def test_old_tables_get_the_best_effort_columns(store):
    with store.connect() as conn:
        conn.execute(runs.TABLES)
    runs.ensure_tables(store)
    with store.connect() as conn:
        names = {r["name"] for r in conn.execute("PRAGMA table_info(run)").fetchall()}
    assert {"best_5k_s", "best_10k_s", "best_half_s", "bests_checked", *runs.PLACE} <= names


def test_runs_kept_before_best_efforts_get_them(store):
    runs.receive(store, {"data": {"workouts": [workout()]}})
    with store.connect() as conn:  # as step 1 kept it: no bests
        conn.execute("UPDATE run SET best_5k_s = NULL, best_10k_s = NULL, best_half_s = NULL, "
                     "bests_checked = 0")
    listed = runs.since(store, "2000-01-01T00:00:00+00:00")
    assert listed[0]["bests"]["5k"] == pytest.approx(1650, abs=10)
    assert runs.fill_bests(store) == 0  # done once


def test_a_run_whose_route_has_no_5_km_is_searched_once(store):
    """The watch says 8 km, the route covers less (GPS cut short): no best, and no search of
    its route again on every request (which kept the hub busy)."""
    runs.receive(store, {"data": {"workouts": [workout(distance={"qty": 8, "units": "km"},
                                                       route=route(km=3))]}})
    with store.connect() as conn:  # kept before the check was stored
        conn.execute("UPDATE run SET bests_checked = 0")
    assert runs.fill_bests(store) == 1
    assert runs.since(store, "2000-01-01T00:00:00+00:00")[0]["bests"]["5k"] is None
    assert runs.fill_bests(store) == 0


def test_the_drawn_pace_rides_over_gps_jitter():
    # Evenly spaced points every 50 m whose times jitter: 5 s, then 25 s, and so on (5:00/km).
    points, t = [], 0
    for i in range(201):
        points.append([52.5 + i * 50 / 111_195, 3.5, 0.0, t, 0.0])
        t += 5 if i % 2 == 0 else 25
    paces = [p[2] for p in runs.paced(points, 200)[1:]]
    # One stretch alone swings from 1:40 to 8:20 a km; drawn, nearly all read the true 5:00.
    near = [p for p in paces if 285 <= p <= 315]
    assert len(near) >= 0.95 * len(paces) and max(paces) - min(paces) <= 80
