from __future__ import annotations

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from fastapi.testclient import TestClient

from app import desk, main

ZONE = ZoneInfo("Europe/Amsterdam")
NOW = datetime(2026, 10, 19, 5, 0, tzinfo=UTC)  # 07:00 in Amsterdam, summer time
CFG = {"timezone": "Europe/Amsterdam"}


def rain(*values: float) -> list[dict]:
    return [{"at": (NOW + timedelta(minutes=5 * i)).isoformat(), "mm_per_hour": v}
            for i, v in enumerate(values)]


def weather(points, stale=False) -> dict:
    return {"as_of": NOW.isoformat(), "stale": stale, "station": "Meetstation De Bilt",
            "temperature": 13.6, "description": "Zwaar bewolkt", "rain": points}


def test_the_rain_line_is_worded_as_on_home():
    assert desk.rain_line([], ZONE) == "No rain forecast available"
    assert desk.rain_line(rain(0, 0.05, 0), ZONE) == "Dry for the next 2 hours"
    assert desk.rain_line(rain(0, 0, 1.24, 2.8, 0), ZONE) == "Rain from 07:10, up to 2,8 mm/h"
    assert desk.rain_line(rain(0.6, 0.4, 0), ZONE) == "Rain now, up to 0,6 mm/h; dry from 07:10"
    assert desk.rain_line(rain(0.6, 0.4), ZONE) == "Rain for the next 2 hours, up to 0,6 mm/h"


def test_the_now_panel_gets_its_clock_and_the_hubs_time(store):
    store.put_cache("weather", weather(rain(0, 0, 1.24, 2.8, 0)))

    answer = desk.answer(CFG, store, "now", NOW)

    assert answer["time"] == {"epoch": NOW.timestamp(), "utc_offset": 7200}
    (clock,) = answer["screens"]
    assert clock == {
        "kind": "clock", "stale": False, "place": "De Bilt", "date": "Mon 19 Oct",
        "temperature": 14, "description": "Zwaar bewolkt", "rain": [0, 0, 1.24, 2.8, 0],
        "rain_line": "Rain from 07:10, up to 2,8 mm/h", "wet": True}
    assert answer["stale"] is False


def test_winter_time_moves_the_offset(store):
    winter = datetime(2026, 12, 1, 6, 0, tzinfo=UTC)
    assert desk.answer(CFG, store, "now", winter)["time"]["utc_offset"] == 3600


def test_stale_or_missing_weather_marks_the_screen(store):
    assert desk.answer(CFG, store, "now", NOW)["screens"][0]["stale"] is True
    store.put_cache("weather", weather(rain(0), stale=True))
    answer = desk.answer(CFG, store, "now", NOW)
    assert answer["stale"] is True and answer["screens"][0]["temperature"] == 14


def test_the_route_and_its_panel_names(store):
    main.app.state.store = store
    main.app.state.config = CFG
    client = TestClient(main.app)

    assert client.get("/api/desk/test").json()["screens"][0]["kind"] == "clock"
    assert client.get("/api/desk/home").json()["screens"] == []
    assert client.get("/api/desk/kitchen").status_code == 422
