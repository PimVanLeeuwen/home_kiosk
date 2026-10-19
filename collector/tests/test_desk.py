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
    store.put_cache("forecast", forecast(dry_day()))

    answer = desk.answer(CFG, store, "now", NOW)

    assert answer["time"] == {"epoch": NOW.timestamp(), "utc_offset": 7200}
    clock, day = answer["screens"]
    assert day["kind"] == "day"
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


def hours(temps: dict[int, float] | None = None, rain_at: dict[int, int] | None = None) -> list:
    temps, rain_at = temps or {}, rain_at or {}
    return [{"hour": h, "temperature": temps.get(h, 10 + (5 if 12 <= h <= 17 else 0)),
             "rain_chance": rain_at.get(h, 0)} for h in range(24)]


def dry_day(date="2026-10-19", **kw) -> dict:
    return {"date": date, "high": 15.4, "low": 9.4, "sunrise": "08:08", "sunset": "18:36",
            "hours": hours(**kw)}


def forecast(*days, stale=False) -> dict:
    return {"as_of": NOW.isoformat(), "stale": stale, "days": list(days)}


def test_the_day_view_from_six_to_midnight(store):
    store.put_cache("forecast", forecast(dry_day(temps={16: 15.4}),
                                         dry_day("2026-10-20", temps={14: 12.2})))

    day = desk.day_screen(store, ZONE, NOW)  # 07:00

    assert (day["title"], day["high"], day["low"], day["stale"]) == ("Your day", 15, 9, False)
    assert len(day["temperatures"]) == 19 and len(day["rain"]) == 19
    assert (day["sunrise_minute"], day["sunset_minute"], day["now_minute"]) == (488, 1116, 420)
    assert (day["lead"], day["rest"]) == ("Dry for the rest of the day,",
                                          "15° at its warmest around 16:00.")
    assert day["credit"] == "Open-Meteo"


def test_late_in_the_evening_it_shows_tomorrow(store):
    store.put_cache("forecast", forecast(dry_day(), dry_day("2026-10-20")))
    evening = datetime(2026, 10, 19, 18, 30, tzinfo=UTC)  # 20:30 in Amsterdam

    day = desk.day_screen(store, ZONE, evening)

    assert (day["title"], day["now_minute"], day["lead"]) == ("Tomorrow", None, "Dry all day,")


def test_the_sentence_follows_the_rain():
    wet = hours(rain_at={14: 60, 15: 80, 16: 55, 17: 20})
    assert desk.day_sentence(wet, 9) == ("Rain likely from 14:00,", "dry again from 17:00.")
    assert desk.day_sentence(wet, 14) == ("Rain likely now,", "dry again from 17:00.")
    late = hours(rain_at={22: 70, 23: 90})
    assert desk.day_sentence(late, 9) == ("Rain likely from 22:00,", "until the end of the day.")
    maybe = hours(rain_at={11: 35, 12: 45})
    assert desk.day_sentence(maybe, 9) == ("A chance of showers around 12:00,", "45% at most.")
    assert desk.day_sentence(hours(), 19) == ("Dry for the rest of the day,",
                                              "cooling to 10° tonight.")


def test_no_forecast_yet_is_a_stale_day(store):
    day = desk.day_screen(store, ZONE, NOW)
    assert (day["present"], day["stale"]) == (False, True)


def test_the_route_and_its_panel_names(store):
    main.app.state.store = store
    main.app.state.config = CFG
    client = TestClient(main.app)

    assert client.get("/api/desk/test").json()["screens"][0]["kind"] == "clock"
    assert client.get("/api/desk/home").json()["screens"] == []
    assert client.get("/api/desk/kitchen").status_code == 422
