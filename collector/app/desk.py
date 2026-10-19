"""What each desk panel shows (plan.md M16): `/api/desk/<name>`.

A panel only knows its name. Every answer carries the hub's time (the panels
take their clock from it and never contact the internet) and the panel's
screens, each a small block of ready-to-draw values: wording, rounding and
local times are done here, so the firmware stays simple.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from zoneinfo import ZoneInfo

from .sources import weather
from .store import Store

# Below this Buienradar's forecast is drizzle at most: counted as dry (as on Home).
WET_MM = 0.1


def _mm(n: float) -> str:
    return f"{n:.1f}".replace(".", ",")


def rain_line(points: list[dict[str, Any]], zone: ZoneInfo) -> str:
    """One line on the next two hours, worded as on Home (web/src/lib/rain.ts)."""
    if not points:
        return "No rain forecast available"

    def wet(p: dict[str, Any]) -> bool:
        return p["mm_per_hour"] >= WET_MM

    def hhmm(p: dict[str, Any]) -> str:
        return datetime.fromisoformat(p["at"]).astimezone(zone).strftime("%H:%M")

    peak = max(p["mm_per_hour"] for p in points)
    if not any(wet(p) for p in points):
        return "Dry for the next 2 hours"
    if wet(points[0]):
        dry = next((p for p in points if not wet(p)), None)
        if dry:
            return f"Rain now, up to {_mm(peak)} mm/h; dry from {hhmm(dry)}"
        return f"Rain for the next 2 hours, up to {_mm(peak)} mm/h"
    first = next(p for p in points if wet(p))
    return f"Rain from {hhmm(first)}, up to {_mm(peak)} mm/h"


def clock_screen(store: Store, zone: ZoneInfo, now: datetime) -> dict[str, Any]:
    """The Now panel's clock: the next two hours of rain as a ring around the time."""
    w = store.get_cache(weather.CACHE_KEY) or {}
    points = w.get("rain") or []
    temperature = w.get("temperature")
    station = (w.get("station") or "").removeprefix("Meetstation ").strip()
    return {
        "kind": "clock",
        "stale": bool(w.get("stale")) or not w,
        "place": station or "Buienradar",
        "date": now.astimezone(zone).strftime("%a %-d %b"),
        "temperature": round(temperature) if temperature is not None else None,
        "description": w.get("description"),
        # One value per five minutes from now, as the ring's segments.
        "rain": [round(p["mm_per_hour"], 2) for p in points],
        "rain_line": rain_line(points, zone),
        "wet": any(p["mm_per_hour"] >= WET_MM for p in points),
    }


SCREENS = {"now": (clock_screen,), "home": (), "house": (), "test": (clock_screen,)}


def answer(cfg: dict[str, Any], store: Store, name: str,
           now: datetime | None = None) -> dict[str, Any]:
    zone = ZoneInfo(cfg.get("timezone", "UTC"))
    now = now or datetime.now(UTC)
    screens = [make(store, zone, now) for make in SCREENS[name]]
    return {
        "name": name,
        "as_of": now.isoformat(),
        "stale": any(s["stale"] for s in screens),
        # The panel's clock: seconds since 1970 (UTC) and the local offset now.
        "time": {"epoch": round(now.timestamp(), 3),
                 "utc_offset": int(now.astimezone(zone).utcoffset().total_seconds())},
        "screens": screens,
    }
