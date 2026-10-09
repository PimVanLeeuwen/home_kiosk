from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import httpx
import pytest

from app.sources import weather

AMS = ZoneInfo("Europe/Amsterdam")
NOW = datetime(2026, 10, 9, 12, 48, tzinfo=UTC)  # 14:48 in Amsterdam
FEED = {"actual": {
    "sunrise": "2026-10-09T07:51:00", "sunset": "2026-10-09T18:57:00",
    "stationmeasurements": [
        {"stationname": "Meetstation Rotterdam", "temperature": 14.0},
        {"stationname": "Meetstation De Bilt", "timestamp": "2026-10-09T14:30:00",
         "weatherdescription": "Zwaar bewolkt", "temperature": 12.9, "feeltemperature": 10.6,
         "windspeedBft": 4, "winddirection": "ZW", "humidity": 94.0, "rainFallLastHour": 0.0},
    ]}}


def test_rain_values_become_millimetres_per_hour():
    assert weather.mm_per_hour(0) == 0.0
    assert weather.mm_per_hour(77) == 0.1
    assert weather.mm_per_hour(109) == 1.0
    assert weather.mm_per_hour(141) == 10.0


def test_the_forecast_crosses_midnight():
    late = datetime(2026, 10, 9, 21, 50, tzinfo=UTC)  # 23:50 in Amsterdam
    points = weather.parse_rain("000|23:55\n077|00:00\n000|00:05\nbroken line\n", late, AMS)

    assert [p.at.isoformat() for p in points] == [
        "2026-10-09T23:55:00+02:00", "2026-10-10T00:00:00+02:00", "2026-10-10T00:05:00+02:00"]
    assert [p.mm_per_hour for p in points] == [0.0, 0.1, 0.0]


def test_collects_the_station_and_the_rain():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "gpsgadget.buienradar.nl":
            assert request.url.params["lat"] == "52.11"
            return httpx.Response(200, text="000|14:50\n109|14:55\n")
        return httpx.Response(200, json=FEED)

    w = asyncio.run(weather.collect({"timezone": "Europe/Amsterdam"},
                                    transport=httpx.MockTransport(handler), now=NOW))

    assert (w.station, w.description, w.temperature, w.feel_temperature, w.wind_bft,
            w.wind_direction) == ("Meetstation De Bilt", "Zwaar bewolkt", 12.9, 10.6, 4, "ZW")
    assert w.measured_at.isoformat() == "2026-10-09T14:30:00+02:00"
    assert w.sunset.isoformat() == "2026-10-09T18:57:00+02:00"
    assert [p.mm_per_hour for p in w.rain] == [0.0, 1.0]


def test_an_unknown_station_is_an_error():
    with pytest.raises(ValueError, match="Meetstation Nergens"):
        weather.parse_feed(FEED, "Meetstation Nergens", AMS)
