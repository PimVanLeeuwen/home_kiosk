"""Weather at one spot from Buienradar: rain in the next 2 hours and the
current measurements of the nearest station.

    gpsgadget.buienradar.nl/data/raintext?lat=..&lon=..   "077|15:05" per line,
        24 lines of 5 minutes; mm/h = 10 ** ((value - 109) / 32), 0 is dry
    data.buienradar.nl/2.0/feed/json   actual.stationmeasurements, sunrise, sunset

Only the collector talks to Buienradar; the browser gets this payload. Times in
both feeds are local (Europe/Amsterdam) without a zone. Buienradar's terms ask
for attribution, which the Home tile gives. Their icons live on their CDN, so the
tile uses their description instead.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import httpx

from ..models import RainPoint, Weather

log = logging.getLogger(__name__)

CACHE_KEY = "weather"
RAIN_URL = "https://gpsgadget.buienradar.nl/data/raintext"
FEED_URL = "https://data.buienradar.nl/2.0/feed/json"
TIMEOUT_SECONDS = 15


def settings(cfg: dict[str, Any]) -> dict[str, Any]:
    w = cfg.get("weather") or {}
    return {"lat": float(w.get("lat", 52.11)), "lon": float(w.get("lon", 5.18)),
            "station": str(w.get("station", "Meetstation De Bilt")),
            "enabled": w.get("enabled", True) is not False}


def mm_per_hour(value: int) -> float:
    return 0.0 if value <= 0 else round(10 ** ((value - 109) / 32), 2)


def parse_rain(text: str, now: datetime, zone: ZoneInfo) -> list[RainPoint]:
    """The forecast lines, as moments from now on. A time earlier than the one
    before it is past midnight."""
    local_now = now.astimezone(zone)
    day, previous, points = local_now.date(), None, []
    for line in text.splitlines():
        value, _, hhmm = line.strip().partition("|")
        if not hhmm:
            continue
        try:
            at = time.fromisoformat(hhmm)
            amount = int(value)
        except ValueError:
            continue
        if previous is not None and at < previous:
            day += timedelta(days=1)
        elif previous is None and local_now.hour == 23 and at.hour == 0:
            day += timedelta(days=1)
        previous = at
        points.append(RainPoint(at=datetime.combine(day, at, tzinfo=zone),
                                mm_per_hour=mm_per_hour(amount)))
    return points


def _local(value: str | None, zone: ZoneInfo) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=zone)


def parse_feed(feed: dict[str, Any], station: str, zone: ZoneInfo) -> dict[str, Any]:
    actual = feed.get("actual") or {}
    found = next((s for s in actual.get("stationmeasurements") or []
                  if s.get("stationname") == station), None)
    if found is None:
        raise ValueError(f"no station called {station} in the Buienradar feed")
    return {
        "measured_at": _local(found.get("timestamp"), zone),
        "description": found.get("weatherdescription"),
        "temperature": found.get("temperature"),
        "feel_temperature": found.get("feeltemperature"),
        "wind_bft": found.get("windspeedBft"),
        "wind_direction": found.get("winddirection"),
        "humidity": found.get("humidity"),
        "rain_last_hour": found.get("rainFallLastHour"),
        "sunrise": _local(actual.get("sunrise"), zone),
        "sunset": _local(actual.get("sunset"), zone),
    }


async def collect(cfg: dict[str, Any], transport: httpx.AsyncBaseTransport | None = None,
                  now: datetime | None = None) -> Weather:
    """`transport` and `now` are for tests."""
    w = settings(cfg)
    zone = ZoneInfo(cfg.get("timezone", "Europe/Amsterdam"))
    now = now or datetime.now(UTC)
    async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS, transport=transport) as client:
        rain = await client.get(RAIN_URL, params={"lat": w["lat"], "lon": w["lon"]})
        rain.raise_for_status()
        feed = await client.get(FEED_URL)
        feed.raise_for_status()
    return Weather(as_of=now, station=w["station"], rain=parse_rain(rain.text, now, zone),
                   **parse_feed(feed.json(), w["station"], zone))
