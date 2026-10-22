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
from .desk_clock import clock_screen
from .desk_code import code_screen
from .desk_headlines import headlines_screen
from .desk_home import (
    air_screen,
    apple_screen,
    laundry_screen,
    lights_screen,
    music_screen,
    playing_screen,
)
from .desk_movers import movers_screen
from .desk_pipelines import house_pipelines
from .desk_services import services_screen
from .desk_sites import sites_screen
from .desk_train import train_screen
from .sources import forecast, hue
from .store import Store

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
HOME = (lights_screen, air_screen, laundry_screen, apple_screen)
HOUSE = (code_screen, sites_screen, services_screen, movers_screen)
SCREENS = {"now": NOW, "home": HOME, "house": HOUSE, "test": NOW}
# Panels that turn through their screens on their own; Home decides per answer (home_rules).
ROTATES = {"now": True, "house": True, "test": True}


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


Screens = list[dict[str, Any]]


def home_rules(screens: Screens, lights_off: bool) -> tuple[Screens, bool]:
    """Home's screens and whether it rotates (the owner's wish, 2026-10-21): while music
    plays it stays on Now Playing (swiped, back there after a quiet minute), even with
    the lights off; with nothing playing and every light off it shows only the light
    controls; otherwise it turns through its screens like the other panels."""
    playing = next((s for s in screens if s["kind"] == "playing"), {})
    if playing.get("present") and playing.get("playing"):
        return screens, False
    if lights_off:
        return [s for s in screens if s["kind"] == "lights"], False
    return screens, True


def answer(cfg: dict[str, Any], store: Store, name: str | None,
           now: datetime | None = None, board: str | None = None,
           music: dict[str, Any] | None = None) -> dict[str, Any]:
    """The screens of panel `name`. A board (asking by its MAC) without a panel
    gets the screen that asks to assign it; one whose panel has no screens yet,
    a screen that says so. The Home panel's music screens need `music`."""
    zone = ZoneInfo(cfg.get("timezone", "UTC"))
    now = now or datetime.now(UTC)
    screens = [make(store, zone, now) for make in SCREENS[name]] if name else []
    rotate = ROTATES.get(name or "", True)
    lights_off = dim(store)
    if name == "home":
        # What plays comes first; the favourites last (`music`: the hub's Spotify state).
        screens = [playing_screen(music, now), *screens, music_screen(music)]
        screens, rotate = home_rules(screens, lights_off)
    if name == "house":
        # A running pipeline takes House over, alone (plan.md M21); otherwise its idle
        # card turns along with House's other screens.
        shown, rotate = house_pipelines(store, zone, now)
        taking_over = any(s["kind"] == "pipeline" for s in shown)
        screens = shown if taking_over else [*shown, *screens]
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
        "dim": lights_off,
        "rotate": rotate,
    }
