from __future__ import annotations

import asyncio
from datetime import UTC, datetime

import httpx

from app.sources import forecast

ANSWER = {
    "hourly": {"time": ["2026-10-19T06:00", "2026-10-19T07:00", "2026-10-20T06:00"],
               "temperature_2m": [9.8, None, 6.1], "precipitation_probability": [0, 20, 55]},
    "daily": {"time": ["2026-10-19", "2026-10-20"], "temperature_2m_max": [15.5, 12.2],
              "temperature_2m_min": [9.4, 6.2], "sunrise": ["2026-10-19T08:08", "2026-10-20T08:10"],
              "sunset": ["2026-10-19T18:36", "2026-10-20T18:34"]},
}


def test_reads_the_days_and_their_hours():
    today, tomorrow = forecast.parse(ANSWER)

    assert (today.date, today.high, today.low, today.sunrise, today.sunset) == (
        "2026-10-19", 15.5, 9.4, "08:08", "18:36")
    assert [(h.hour, h.temperature, h.rain_chance) for h in today.hours] == [(6, 9.8, 0)]
    assert [(h.hour, h.rain_chance) for h in tomorrow.hours] == [(6, 55)]


def test_asks_for_the_weather_place_in_local_time():
    asked = []

    def handler(request):
        asked.append(dict(request.url.params))
        return httpx.Response(200, json=ANSWER)

    cfg = {"timezone": "Europe/Amsterdam", "weather": {"lat": 52.11, "lon": 5.18}}
    result = asyncio.run(forecast.collect(cfg, httpx.MockTransport(handler),
                                          datetime(2026, 10, 19, 5, tzinfo=UTC)))

    assert len(result.days) == 2
    assert asked[0]["latitude"] == "52.11" and asked[0]["timezone"] == "Europe/Amsterdam"
    assert asked[0]["forecast_days"] == "2"
