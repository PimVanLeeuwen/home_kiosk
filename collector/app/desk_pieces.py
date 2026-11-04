"""The pieces (plan.md M27, step 4): screens that are a painted picture with a few words
on it. Each builder gives the words and where they go; its painter (app/paint_*.py) the
picture. The panel shows any of them with one screen (panels/firmware/main/screen_piece.c).

A label: text, x, y, width, font ("24", "28" bold, "40", "52" bold, "clock" 150, "digits"
84), align ("left", "centre" or "right", where x is that edge or the middle), colour (hex,
no #), lines (at most, cut with "..." after) and spacing (for the small capitals).
"""

from __future__ import annotations

import math
from datetime import UTC, date, datetime
from typing import Any
from zoneinfo import ZoneInfo

from .desk_clock import _local, _phase, clock_screen, condition
from .panel_text import latin1
from .sources import countdown, photo, radar, weather
from .store import Store


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


def _days_word(n: int) -> str:
    return f"{n} day{'s' if n != 1 else ''}"


def countdown_screen(store: Store, zone: ZoneInfo, now: datetime) -> dict[str, Any]:
    """K, the countdown: the days to the nearest event marked "⏳" or "#countdown"."""
    cached = store.get_cache(countdown.CACHE_KEY) or {}
    today = now.astimezone(zone).date()
    ahead = [e for e in cached.get("events") or [] if date.fromisoformat(e["date"]) >= today]
    if not ahead:
        return absent("countdown")
    first = ahead[0]
    day = date.fromisoformat(first["date"])
    days = (day - today).days
    labels = [
        caps("Countdown", 36, 24, width=300),
        caps(day.strftime("%a %-d %b"), 684, 24, width=300, align="right"),
        label(latin1(first["title"]), 360, 586, font="40", align="centre"),
    ]
    if days == 0:
        labels.append(label("Today", 360, 470, width=400, font="52", align="centre"))
    else:
        labels += [label(str(days), 360, 404, width=400, font="clock", align="centre"),
                   label(f"day{'s' if days != 1 else ''} to", 360, 544, font="28",
                         align="centre", colour="c9c6d6")]
    if len(ahead) > 1:
        then = ahead[1]
        left = (date.fromisoformat(then["date"]) - today).days
        labels.append(label(f"Then {latin1(then['title'])} in {_days_word(left)}", 360, 646,
                            align="centre", colour="9a9fb8"))
    return {"kind": "countdown", "stale": bool(cached.get("stale")), "present": True,
            "days": days, "colour": first["colour"], "labels": labels}


# 250 and 420, the lows a range in front between 480 and 600.
def radar_screen(store: Store, zone: ZoneInfo, now: datetime) -> dict[str, Any]:
    """I, the rain radar: while rain is expected within two hours, Buienradar's radar round
    home, the next two hours as bars and the Clock's rain line."""
    cached = store.get_cache(radar.CACHE_KEY) or {}
    if not radar.wet(store) or radar.FRAMES.rain is None or not cached.get("stamp"):
        return absent("radar")
    clock = clock_screen(store, zone, now)
    frame = datetime.strptime(cached["stamp"], "%Y%m%d%H%M").replace(tzinfo=UTC)
    labels = [
        caps("Rain radar", 36, 24, width=300),
        caps(f"Buienradar · {frame.astimezone(zone):%H:%M}", 684, 24, width=400, align="right"),
        label(clock.get("rain_line") or "", 36, 556, font="28", colour="9cc0f0"),
    ]
    for i, text in enumerate((clock.get("rain_axis") or [])[:3]):
        labels.append(label(text, [36, 360, 684][i], 670, width=200,
                            align=["left", "centre", "right"][i], colour="9a9fb8"))
    return {"kind": "radar", "stale": clock["stale"], "present": True,
            "stamp": cached["stamp"], "home": cached.get("home") or [250, 256],
            "rain": clock.get("rain") or [], "labels": labels}


def photo_screen(store: Store, zone: ZoneInfo, now: datetime) -> dict[str, Any]:
    """E, the photo of the day: an "on this day" picture from Immich, on a frosted label
    saying how long ago and who is in it."""
    cached = store.get_cache(photo.CACHE_KEY) or {}
    if not cached.get("asset") or photo.KEPT.picture is None:
        return absent("photo")
    if cached.get("taken", "")[5:] != now.astimezone(zone).date().isoformat()[5:]:
        return absent("photo")  # yesterday's still, until this morning's is read
    years = cached.get("years") or 0
    taken = date.fromisoformat(cached["taken"])
    people = cached.get("people") or []
    line = taken.strftime("%-d %B %Y") + (f" · {', '.join(latin1(p) for p in people)}"
                                         if people else "")
    return {
        "kind": "photo", "stale": bool(cached.get("stale")), "present": True,
        "asset": cached["asset"],
        "labels": [
            label(f"{years} year{'s' if years != 1 else ''} ago today" if years else "Today",
                  60, 584, width=600, font="40"),
            label(line, 60, 636, width=600, colour="e6e3ef"),
        ],
    }
