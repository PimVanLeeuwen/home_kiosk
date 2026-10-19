"""Today's and tomorrow's weather by the hour, from Open-Meteo, for the Now
panel's day view (plan.md M20).

    api.open-meteo.com/v1/forecast?latitude=..&longitude=..&hourly=temperature_2m,
        precipitation_probability&daily=temperature_2m_max,temperature_2m_min,
        sunrise,sunset&timezone=Europe/Amsterdam&forecast_days=2

Free, no key, open data (KNMI's and DWD's models for the Netherlands) under
CC BY 4.0: the panel credits Open-Meteo. Only the coordinates of the weather
block in config.yaml are sent (city level). Times come back local.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import httpx
from pydantic import BaseModel

from ..models import Envelope
from . import weather

CACHE_KEY = "forecast"
URL = "https://api.open-meteo.com/v1/forecast"
TIMEOUT_SECONDS = 15


class Hour(BaseModel):
    hour: int  # 0 to 23, local
    temperature: float
    rain_chance: int  # percent


class Day(BaseModel):
    date: str  # YYYY-MM-DD, local
    high: float
    low: float
    sunrise: str | None  # HH:MM, local
    sunset: str | None
    hours: list[Hour]


class Forecast(Envelope):
    days: list[Day]


def _hhmm(value: str | None) -> str | None:
    return value[11:16] if value and len(value) >= 16 else None


def parse(answer: dict[str, Any]) -> list[Day]:
    hourly, daily = answer.get("hourly") or {}, answer.get("daily") or {}
    by_date: dict[str, list[Hour]] = {}
    for at, temperature, chance in zip(hourly.get("time") or [],
                                       hourly.get("temperature_2m") or [],
                                       hourly.get("precipitation_probability") or [], strict=False):
        if temperature is None:
            continue
        by_date.setdefault(at[:10], []).append(
            Hour(hour=int(at[11:13]), temperature=temperature, rain_chance=int(chance or 0)))
    days = []
    for i, date in enumerate(daily.get("time") or []):
        high, low = daily["temperature_2m_max"][i], daily["temperature_2m_min"][i]
        if high is None or low is None:
            continue
        days.append(Day(date=date, high=high, low=low,
                        sunrise=_hhmm(daily.get("sunrise", [None] * (i + 1))[i]),
                        sunset=_hhmm(daily.get("sunset", [None] * (i + 1))[i]),
                        hours=by_date.get(date, [])))
    return days


async def collect(cfg: dict[str, Any], transport: httpx.AsyncBaseTransport | None = None,
                  now: datetime | None = None) -> Forecast:
    w = weather.settings(cfg)
    params = {"latitude": w["lat"], "longitude": w["lon"],
              "hourly": "temperature_2m,precipitation_probability",
              "daily": "temperature_2m_max,temperature_2m_min,sunrise,sunset",
              "timezone": cfg.get("timezone", "UTC"), "forecast_days": 2}
    async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS, transport=transport) as http:
        resp = await http.get(URL, params=params)
        resp.raise_for_status()
        days = parse(resp.json())
    if not days:
        raise ValueError("Open-Meteo answered without a forecast")
    return Forecast(as_of=now or datetime.now(UTC), stale=False, days=days)
