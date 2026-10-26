"""The pieces (plan.md M27, step 4): screens that are a painted picture with a few words
on it. Each builder gives the words and where they go; its painter (app/paint_*.py) the
picture. The panel shows any of them with one screen (panels/firmware/main/screen_piece.c).

A label: text, x, y, width, font ("24", "28" bold, "40", "52" bold, "clock" 150, "digits"
84), align ("left", "centre" or "right", where x is that edge or the middle), colour (hex,
no #), lines (at most, cut with "..." after) and spacing (for the small capitals).
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from .desk_clock import _local, _phase, clock_screen, condition
from .sources import weather
from .store import Store

GOLDEN = timedelta(hours=1)  # golden hour: the hour before sunset
DARK = timedelta(minutes=40)  # after sunset: dusk until then (as the Clock's twilight)


def label(text: str, x: int, y: int, *, width: int = 648, font: str = "24",
          align: str = "left", colour: str = "ffffff", lines: int = 1,
          spacing: int = 0) -> dict[str, Any]:
    return {"text": text, "x": x, "y": y, "width": width, "font": font, "align": align,
            "colour": colour, "lines": lines, "spacing": spacing}


def caps(text: str, x: int, y: int, **kw: Any) -> dict[str, Any]:
    """The small capitals of every panel screen's header row."""
    return label(text.upper(), x, y, colour=kw.pop("colour", "c4c8de"), spacing=2, **kw)


def absent(kind: str) -> dict[str, Any]:
    return {"kind": kind, "stale": False, "present": False}


def _sun(store: Store, zone: ZoneInfo, now: datetime) -> tuple[datetime | None, datetime | None]:
    w = store.get_cache(weather.CACHE_KEY) or {}
    local = now.astimezone(zone)
    rise, down = _local(w.get("sunrise"), zone), _local(w.get("sunset"), zone)
    if rise is None or down is None:
        return None, None
    day = dict(year=local.year, month=local.month, day=local.day)
    return rise.replace(**day), down.replace(**day)


def next_light(local: datetime, rise: datetime | None, down: datetime | None) -> str:
    """What the light does next: "Golden hour from 17:26", "Sunset 18:26", "Dark from 19:06"."""
    if rise is None or down is None:
        return ""
    if local < rise:
        return f"Sunrise {rise:%H:%M}"
    if local < down - GOLDEN:
        return f"Golden hour from {down - GOLDEN:%H:%M}"
    if local < down:
        return f"Sunset {down:%H:%M}"
    if local < down + DARK:
        return f"Dark from {down + DARK:%H:%M}"
    return f"Sunrise {rise + timedelta(days=1):%H:%M}"


def sky_screen(store: Store, zone: ZoneInfo, now: datetime) -> dict[str, Any]:
    """A, the living sky: by day, at dawn and at dusk; the night sky takes over after dark."""
    clock = clock_screen(store, zone, now)
    local = now.astimezone(zone)
    rise, down = _sun(store, zone, now)
    sky = clock.get("horizon") or {}
    if not sky or _phase(local, rise, down) == "night":
        return absent("sky")
    words = clock.get("description") or ""
    temperature = clock.get("temperature")
    weather_line = " · ".join(p for p in (f"{temperature}°" if temperature is not None else "",
                                          words) if p)
    return {
        "kind": "sky", "stale": clock["stale"], "present": True,
        "horizon": sky, "phase": _phase(local, rise, down),
        "labels": [
            caps(local.strftime("%a %-d %b"), 36, 24, width=320),
            caps(clock.get("place") or "", 684, 24, width=320, align="right"),
            label(next_light(local, rise, down), 360, 566, font="28", align="centre",
                  colour="ffffff"),
            label(weather_line, 360, 618, align="centre", colour="c9c6d6"),
        ],
        "clock": label("", 360, 150, font="clock", align="centre", colour="ffffff"),
    }


# Constellations as the night sky draws them (paint_night): which one is up, by season.
def constellation(local: datetime) -> str:
    """Orion on winter nights, the Big Dipper in spring, Cassiopeia otherwise (it never sets
    here)."""
    month, hour = local.month, local.hour
    if month in (11, 12, 1, 2, 3) and (hour >= 21 or hour < 5):
        return "Orion"
    if month in (3, 4, 5, 6):
        return "the Big Dipper"
    return "Cassiopeia"


MOON_NAMES = [(0.03, "New moon"), (0.22, "Waxing crescent"), (0.28, "First quarter"),
              (0.47, "Waxing gibbous"), (0.53, "Full moon"), (0.72, "Waning gibbous"),
              (0.78, "Last quarter"), (0.97, "Waning crescent"), (1.01, "New moon")]


def moon_words(phase: float) -> str:
    """0 new, 0.5 full: "Waxing gibbous, 78% lit"."""
    name = next(n for limit, n in MOON_NAMES if phase < limit)
    lit = round(100 * (1 - math.cos(2 * math.pi * phase)) / 2)
    return f"{name}, {lit}% lit"


def night_screen(store: Store, zone: ZoneInfo, now: datetime) -> dict[str, Any]:
    """B, the night sky: after dark on a clear or partly clear night."""
    clock = clock_screen(store, zone, now)
    local = now.astimezone(zone)
    rise, down = _sun(store, zone, now)
    sky = clock.get("horizon") or {}
    _, kind = condition((store.get_cache(weather.CACHE_KEY) or {}).get("description"))
    if not sky or _phase(local, rise, down) != "night" or kind not in ("clear", "partly", None):
        return absent("night")
    shape = constellation(local)
    return {
        "kind": "night", "stale": clock["stale"], "present": True,
        "horizon": sky, "constellation": shape, "clear": kind == "clear",
        "labels": [
            caps(local.strftime("%a %-d %b"), 36, 24, width=320),
            caps("Tonight", 684, 24, width=320, align="right"),
            label(moon_words(sky["moon"] / 1000), 36, 560, font="28", colour="e6e3ef"),
            label(f"{shape[0].upper()}{shape[1:]} is up", 36, 600, colour="9a9fb8"),
        ],
        "clock": label("", 684, 556, width=300, font="digits", align="right", colour="ffffff"),
    }


def year_screen(store: Store, zone: ZoneInfo, now: datetime) -> dict[str, Any]:
    """H, the year: today's day of it, in the middle of the dial (paint_year)."""
    local = now.astimezone(zone)
    days = 366 if local.year % 4 == 0 and (local.year % 100 or local.year % 400 == 0) else 365
    today = local.timetuple().tm_yday
    left = days - today
    return {
        "kind": "year", "stale": False, "present": True,
        "year": local.year, "today": today, "days": days,
        "labels": [
            caps(f"The year · {local.year}", 36, 24, width=400),
            caps(local.strftime("%a %-d %b"), 684, 24, width=300, align="right"),
            label(str(today), 360, 300, width=300, font="52", align="centre"),
            label(f"of {days}", 360, 362, width=300, align="centre", colour="9a9fb8"),
            label(f"{left} day{'s' if left != 1 else ''} left this year", 360, 650,
                  font="28", align="centre", colour="e6e3ef"),
        ],
    }


SEASONS = {12: "winter", 1: "winter", 2: "winter", 3: "spring", 4: "spring", 5: "spring",
           6: "summer", 7: "summer", 8: "summer", 9: "autumn", 10: "autumn", 11: "autumn"}


def art_screen(store: Store, zone: ZoneInfo, now: datetime) -> dict[str, Any]:
    """F, the art of the day: a new piece each morning, numbered by the day of the year."""
    local = now.astimezone(zone)
    number = local.timetuple().tm_yday
    season = SEASONS[local.month]
    return {
        "kind": "art", "stale": False, "present": True,
        "day": local.date().toordinal(), "season": season,
        "labels": [
            caps("Art of the day", 36, 24, width=400),
            caps(f"No. {number}", 684, 24, width=300, align="right"),
            label(f"Flow field, {season}", 36, 662, colour="c9c6d6"),
        ],
    }


def orbit_screen(store: Store, zone: ZoneInfo, now: datetime) -> dict[str, Any]:
    """C, the orbit clock (House): the panel moves the hour, the minute and the second
    round the sun (panels/firmware/main/screen_piece.c); the hub paints the sky."""
    local = now.astimezone(zone)
    return {
        "kind": "orbit", "stale": False, "present": True,
        "labels": [
            caps("Orbit", 36, 24, width=300),
            caps(local.strftime("%a %-d %b"), 684, 24, width=300, align="right"),
        ],
        "clock": label("", 360, 662, width=300, font="28", align="centre", colour="c9c6d6"),
    }
