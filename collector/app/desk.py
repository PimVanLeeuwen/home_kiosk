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

from .desk_agenda import agenda_screen
from .desk_headlines import headlines_screen
from .desk_home import (
    apple_screen,
    laundry_screen,
    lights_screen,
    music_screen,
    playing_screen,
)
from .desk_train import train_screen
from .sources import forecast, hue, weather
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


# The day view looks at tomorrow from this hour on.
TOMORROW_FROM = 20
LIKELY, MAYBE = 50, 30  # chance of rain, %


def day_sentence(hours: list[dict[str, Any]], start: int) -> tuple[str, str]:
    """Two parts, the first brighter: what the rain does, then the rest."""
    ahead = [h for h in hours if h["hour"] >= start] or hours
    likely = [h for h in ahead if h["rain_chance"] >= LIKELY]
    maybe = [h for h in ahead if h["rain_chance"] >= MAYBE]
    if likely:
        first = likely[0]["hour"]
        end = first
        while any(h["hour"] == end + 1 and h["rain_chance"] >= LIKELY for h in ahead):
            end += 1
        lead = "Rain likely now," if first == start else f"Rain likely from {first:02d}:00,"
        rest = f"dry again from {end + 1:02d}:00." if end < 23 else "until the end of the day."
        return lead, rest
    if maybe:
        peak = max(maybe, key=lambda h: h["rain_chance"])
        return (f"A chance of showers around {peak['hour']:02d}:00,",
                f"{peak['rain_chance']}% at most.")
    lead = "Dry all day," if start <= 6 else "Dry for the rest of the day,"
    warmest = max(ahead, key=lambda h: h["temperature"])
    if warmest["hour"] > start:
        warm = round(warmest["temperature"])
        return lead, f"{warm}° at its warmest around {warmest['hour']:02d}:00."
    coolest = min(ahead, key=lambda h: h["temperature"])
    return lead, f"cooling to {round(coolest['temperature'])}° tonight."


def _minutes(hhmm: str | None) -> int | None:
    return int(hhmm[:2]) * 60 + int(hhmm[3:5]) if hhmm else None


def day_screen(store: Store, zone: ZoneInfo, now: datetime) -> dict[str, Any]:
    """The Now panel's day view: the sun's arc over the sky, the temperature from
    06:00 to midnight and the chance of rain, for today or, late, tomorrow."""
    f = store.get_cache(forecast.CACHE_KEY) or {}
    days = f.get("days") or []
    local = now.astimezone(zone)
    tomorrow = local.hour >= TOMORROW_FROM and len(days) > 1
    day = days[1] if tomorrow else (days[0] if days else None)
    if day is None:
        return {"kind": "day", "stale": True, "title": "Your day", "present": False}
    by_hour = {h["hour"]: h for h in day["hours"]}
    # 06:00 to 24:00: nineteen points, midnight repeating the last hour.
    points = [by_hour.get(min(h, 23)) or by_hour.get(23) for h in range(6, 25)]
    points = [p for p in points if p]
    start = 6 if tomorrow else max(6, local.hour)
    lead, rest = day_sentence(day["hours"], start)
    return {
        "kind": "day",
        "stale": bool(f.get("stale")),
        "present": True,
        "title": "Tomorrow" if tomorrow else "Your day",
        "high": round(day["high"]),
        "low": round(day["low"]),
        "lead": lead,
        "rest": rest,
        "temperatures": [round(p["temperature"], 1) for p in points],
        "rain": [p["rain_chance"] for p in points],
        "sunrise": day["sunrise"],
        "sunset": day["sunset"],
        "sunrise_minute": _minutes(day["sunrise"]),
        "sunset_minute": _minutes(day["sunset"]),
        # Where the now line goes; none when the view shows tomorrow.
        "now_minute": None if tomorrow else local.hour * 60 + local.minute,
        "credit": "Open-Meteo",
    }


def _headlines(store: Store, zone: ZoneInfo, now: datetime) -> dict[str, Any]:
    return headlines_screen(store, now)


NOW = (clock_screen, train_screen, agenda_screen, day_screen, _headlines)
HOME = (lights_screen, laundry_screen, apple_screen)
SCREENS = {"now": NOW, "home": HOME, "house": (), "test": NOW}
# Panels that turn through their screens on their own; Home is swiped instead.
ROTATES = {"now": True, "home": False, "house": True, "test": True}


def board_screen(mac: str, title: str, hint: str) -> dict[str, Any]:
    """A board's own screen: its MAC address (as written on its back) and what
    to do, for a board without a panel or a panel without screens yet."""
    return {"kind": "board", "stale": False, "mac": mac, "title": title, "hint": hint}


UNASSIGNED = ("Which panel is this?", "Choose it in the hub: Settings, Desk panels.")


def dim(store: Store) -> bool:
    """The panels dim while every living room light is off (the owner's wish,
    2026-10-20), and stay bright when the hub cannot tell (no or stale lights)."""
    lights = store.get_cache(hue.CACHE_KEY)
    if not lights or lights.get("stale") or not lights.get("groups"):
        return False
    return not any(light.get("on") for group in lights["groups"]
                   for light in group.get("lights") or [])


def answer(cfg: dict[str, Any], store: Store, name: str | None,
           now: datetime | None = None, board: str | None = None,
           music: dict[str, Any] | None = None) -> dict[str, Any]:
    """The screens of panel `name`. A board (asking by its MAC) without a panel
    gets the screen that asks to assign it; one whose panel has no screens yet,
    a screen that says so. The Home panel's music screens need `music`."""
    zone = ZoneInfo(cfg.get("timezone", "UTC"))
    now = now or datetime.now(UTC)
    screens = [make(store, zone, now) for make in SCREENS[name]] if name else []
    if name == "home":
        # What plays comes first; the favourites last (`music`: the hub's Spotify state).
        screens = [playing_screen(music, now), *screens, music_screen(music)]
    if board and name is None:
        screens = [board_screen(board, *UNASSIGNED)]
    elif board and not any(s.get("present", True) for s in screens):
        # No screens yet at all, or none with anything to show yet.
        hint = "Nothing to show yet." if screens else "Its screens come in a later update."
        screens = [*screens, board_screen(board, f"{name.title()} panel", hint)]
    return {
        "name": name,
        "board": board,
        "as_of": now.isoformat(),
        "stale": any(s["stale"] for s in screens),
        # The panel's clock: seconds since 1970 (UTC) and the local offset now.
        "time": {"epoch": round(now.timestamp(), 3),
                 "utc_offset": int(now.astimezone(zone).utcoffset().total_seconds())},
        "screens": screens,
        "dim": dim(store),
        "rotate": ROTATES.get(name or "", True),
    }
