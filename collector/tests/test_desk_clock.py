from __future__ import annotations

import time
from datetime import UTC, datetime, timedelta
from unittest.mock import ANY
from zoneinfo import ZoneInfo

from app import desk_clock

ZONE = ZoneInfo("Europe/Amsterdam")
NOW = datetime(2026, 10, 21, 8, 1, tzinfo=UTC)  # 10:01 in Amsterdam
SUNRISE = datetime(2026, 10, 21, 8, 4, tzinfo=ZONE)
SUNSET = datetime(2026, 10, 21, 18, 41, tzinfo=ZONE)


def local(hour: int, minute: int = 0) -> datetime:
    return datetime(2026, 10, 21, hour, minute, tzinfo=ZONE)


def rain(*values: float) -> list[dict]:
    return [{"at": (NOW + timedelta(minutes=5 * i)).isoformat(), "mm_per_hour": v}
            for i, v in enumerate(values)]


def test_buienradars_words_in_english():
    assert desk_clock.condition("Zwaar bewolkt") == ("Overcast", "cloudy")
    assert desk_clock.condition("Zwaar bewolkt met wat lichte regen") == ("Light rain", "rain")
    assert desk_clock.condition("Mix van opklaringen en hoge bewolking") == (
        "Clouds and clear spells", "partly")
    assert desk_clock.condition("Droog na een enkele bui") == ("Dry after showers", "partly")
    assert desk_clock.condition("Afwisselend bewolkt met onweer") == ("Thunderstorms", "thunder")
    assert desk_clock.condition("Helder") == ("Clear", "clear")


def test_unknown_words_stay_as_buienradar_wrote_them():
    assert desk_clock.condition("Iets heel nieuws") == ("Iets heel nieuws", None)
    assert desk_clock.condition(None) == ("", None)


def test_the_sun_shows_sunset_by_day_and_sunrise_otherwise():
    assert desk_clock.sun(local(10, 1), SUNRISE, SUNSET) == "Sunset 18:41"
    assert desk_clock.sun(local(6, 30), SUNRISE, SUNSET) == "Sunrise 08:04"
    assert desk_clock.sun(local(22, 0), SUNRISE, SUNSET) == "Sunrise 08:04"
    assert desk_clock.sun(local(22, 0), None, None) == ""


def top_at(hour: int, minute: int, sunrise=SUNRISE, sunset=SUNSET) -> str:
    return desk_clock.horizon(local(hour, minute), sunrise, sunset, "clear")["top"]


def test_the_light_turns_at_dawn_and_dusk():
    skies = desk_clock.HORIZON_SKIES
    assert top_at(10, 1) == skies["day"]["clear"][0]
    assert top_at(18, 30) == skies["dusk"]["clear"][0]
    assert top_at(7, 50) == skies["dawn"]["clear"][0]
    assert top_at(23, 40) == skies["night"]["clear"][0]


def test_without_sun_times_the_light_goes_by_the_hour():
    skies = desk_clock.HORIZON_SKIES
    assert top_at(23, 0, None, None) == skies["night"]["clear"][0]
    assert top_at(12, 0, None, None) == skies["day"]["clear"][0]


def test_yesterdays_sun_times_still_place_today():
    yesterday = timedelta(days=1)
    assert desk_clock.sun(local(10, 1), SUNRISE - yesterday, SUNSET - yesterday) == "Sunset 18:41"


def test_the_rain_line_says_when_and_for_how_long():
    assert desk_clock.rain_line([], ZONE) == "No rain forecast available"
    assert desk_clock.rain_line(rain(0, 0.05, 0), ZONE) == "Dry until at least 10:11"
    assert desk_clock.rain_line(rain(0, 0, 1.2, 2.8, 0), ZONE) == "Rain from 10:11, about 10 min"
    assert desk_clock.rain_line(rain(0, 0, 1.2, 2.8), ZONE) == "Rain from 10:11"
    assert desk_clock.rain_line(rain(0.6, 0.4, 0), ZONE) == "Rain until about 10:11"
    assert desk_clock.rain_line(rain(0.6, 0.4), ZONE) == "Rain for the next 2 hours"


def test_the_bars_are_labelled_now_and_by_the_clock():
    assert desk_clock.rain_axis(rain(*[0] * 24), ZONE) == ["Now", "11:01", "12:01"]
    assert desk_clock.rain_axis([], ZONE) == []


def test_the_clock_screen_from_the_hubs_weather(store):
    store.put_cache("weather", {
        "as_of": NOW.isoformat(), "stale": False, "station": "Meetstation De Bilt",
        "temperature": 9.6, "description": "Zwaar bewolkt", "sunrise": "2026-10-21T08:04:00",
        "sunset": "2026-10-21T18:41:00", "rain": rain(0, 0, 0.3, 0)})

    screen = desk_clock.clock_screen(store, ZONE, NOW)

    assert screen == {
        "kind": "clock", "stale": False, "date": "Wed 21 Oct",
        "temperature": 10, "description": "Overcast", "sun": "Sunset 18:41",
        "horizon": ANY, "rain": [0, 0, 0.3, 0],
        "rain_axis": ["Now", "11:01", "12:01"], "rain_line": "Rain from 10:11, about 5 min",
        "wet": True}


def test_sun_times_without_an_offset_are_local_whatever_the_machines_zone(monkeypatch):
    # CI runs in UTC: "08:04" from Buienradar is still 08:04 in Amsterdam.
    monkeypatch.setenv("TZ", "UTC")
    time.tzset()
    try:
        assert desk_clock._local("2026-10-21T08:04:00", ZONE) == SUNRISE
        assert desk_clock._local("2026-10-21T06:04:00+00:00", ZONE) == SUNRISE
        assert desk_clock._local("", ZONE) is None
    finally:
        monkeypatch.undo()
        time.tzset()



def test_the_horizon_sky_by_light_and_weather():
    day = desk_clock.horizon(local(10, 1), SUNRISE, SUNSET, "clear")
    assert (day["top"], day["mid"], day["low"]) == ("0d1d40", "2a5aa8", "6f9fe0")
    assert (day["veiled"], day["stars"], day["rise"], day["set"]) == (
        False, False, "08:04", "18:41")
    assert desk_clock.horizon(local(10, 1), SUNRISE, SUNSET, "rain")["veiled"] is True
    assert desk_clock.horizon(local(18, 30), SUNRISE, SUNSET, "clear")["low"] == "d07a4a"  # dusk
    night = desk_clock.horizon(local(23, 40), SUNRISE, SUNSET, "clear")
    assert night["stars"] is True and night["low"] == "1b2350"
    assert desk_clock.horizon(local(23, 40), SUNRISE, SUNSET, "fog")["stars"] is False


def test_the_sun_by_day_and_the_moon_by_night_along_their_arcs():
    morning = desk_clock.horizon(local(8, 4), SUNRISE, SUNSET, "clear")
    assert (morning["body"], morning["at"]) == ("sun", 0)
    noon = desk_clock.horizon(local(13, 22), SUNRISE, SUNSET, "clear")
    assert noon["body"] == "sun" and 480 <= noon["at"] <= 520
    evening = desk_clock.horizon(local(18, 41), SUNRISE, SUNSET, "clear")
    assert (evening["body"], evening["at"]) == ("sun", 1000)
    late = desk_clock.horizon(local(22, 0), SUNRISE, SUNSET, "clear")
    early = desk_clock.horizon(local(6, 0), SUNRISE, SUNSET, "clear")
    assert late["body"] == early["body"] == "moon" and 0 < late["at"] < early["at"] < 1000


def test_the_moons_phase_from_the_date():
    assert desk_clock.moon_phase(datetime(2000, 1, 6, 18, 14, tzinfo=UTC)) < 0.001  # new
    full = desk_clock.moon_phase(datetime(2000, 1, 21, 6, 0, tzinfo=UTC))  # about full
    assert 0.47 < full < 0.53
    assert desk_clock.horizon(local(10, 1), None, None, None)["body"] == "sun"
