"""The Home panel's screens (plan.md M16 to M18, M20), as ready-to-draw values:
what plays (first, while music plays), the living room's lights, the laundry
while a machine runs or is done, the Apple devices, and the music favourites. The Home panel does
not rotate: it is swiped, and goes back to its first screen after a minute
without a touch.

The music screens come from the hub's Spotify state (app/sources/music.py),
read when a Home board asks; their covers go to the panel as small JPEGs made
from the covers the hub stored (`cover`), never fetched for the panel itself.
"""

from __future__ import annotations

import asyncio
import io
import re
from collections import OrderedDict
from datetime import datetime
from typing import Any, Literal
from zoneinfo import ZoneInfo

from PIL import Image, ImageOps

from .panel_text import latin1
from .sources import air, apple, hue, laundry, spotify
from .store import Store

# How each white looks on a tile and in the row of whites: warm to cool.
TONES = {2200: "#ffb46b", 2700: "#ffc98f", 3500: "#ffdcb4", 4500: "#ffeedd", 6500: "#eef0ff"}
PLAIN_WHITE = "#ffd9a8"  # lamps without a choice of white


def _tone(kelvin: int | None) -> str:
    if kelvin is None:
        return PLAIN_WHITE
    return TONES[min(TONES, key=lambda k: abs(k - kelvin))]


def _line(group: dict[str, Any]) -> str:
    count = len(group.get("lights") or [])
    parts = [f"{count} light{'s' if count != 1 else ''}"]
    if not group.get("on"):
        return f"{parts[0]} · off"
    if group.get("kelvin"):
        parts.append(f"{group['kelvin']} K")
    parts.append(f"{round(group.get('brightness') or 0)}%")
    return " · ".join(parts)


def lights_screen(store: Store, zone: ZoneInfo, now: datetime) -> dict[str, Any]:
    """The living room's groups as tiles to switch and dim, and the whites of
    the group that has them."""
    lights = store.get_cache(hue.CACHE_KEY)
    if not lights or not lights.get("groups"):
        return {"kind": "lights", "stale": False, "present": False}
    groups = lights["groups"]
    every = [x for g in groups for x in g.get("lights") or []]
    lit = sum(1 for x in every if x.get("on"))
    ambiance = next((g for g in groups if g.get("kind") == "ambiance"), None)
    return {
        "kind": "lights", "stale": bool(lights.get("stale")), "present": True,
        "title": latin1(lights.get("room") or "Living room"),
        "count": f"{lit} of {len(every)} lights on" if lit else "All lights off",
        "any_on": lit > 0,
        "groups": [{"id": g["id"], "name": latin1(g["name"]), "line": _line(g),
                    "on": bool(g.get("on")), "brightness": round(g.get("brightness") or 0),
                    "tone": _tone(g.get("kelvin"))} for g in groups[:4]],
        # The row of whites for the group that has a choice (the kitchen spots).
        "whites": None if ambiance is None else {
            "group": ambiance["id"], "name": latin1(ambiance["name"]),
            "kelvin": ambiance.get("kelvin") if ambiance.get("on") else None,
            "choices": [{"kelvin": k, "tone": t} for k, t in TONES.items() if k in hue.KELVINS]},
    }


# --- music -----------------------------------------------------------------------------

COVER_KEY = re.compile(r"^[0-9a-f]{8,64}$")
# Multiples of 16, for the decoder.
CoverSize = Literal["big", "tile", "wall", "thumb"]
COVER_SIZES = {"big": (288, 288), "tile": (320, 256), "wall": (144, 144), "thumb": (96, 96)}
_covers: OrderedDict[tuple[str, str], bytes] = OrderedDict()
KEEP_COVERS = 16


def _cover_path(key: str | None, size: str) -> str | None:
    return f"/api/desk/cover/{key}/{size}" if key else None


def _device_name(device: dict[str, Any] | None, fallback: str) -> str:
    return latin1((device or {}).get("name") or fallback)


def _played_out(music: dict[str, Any], playing: dict[str, Any], now: datetime) -> bool:
    """A last answer, kept while Spotify fails or pauses the hub, that said "playing"
    for a track that has ended since: what plays now is unknown, so Home lets go."""
    if not music.get("stale") or playing.get("state") != "playing":
        return False
    left_ms = (playing.get("duration_ms") or 0) - (playing.get("progress_ms") or 0)
    return (music.get("as_of") or 0) + max(left_ms, 0) / 1000 < now.timestamp()


def playing_screen(music: dict[str, Any] | None, now: datetime) -> dict[str, Any]:
    """Now Playing: shown first on the Home panel while something plays or is paused."""
    playing = (music or {}).get("playing")
    if not playing or _played_out(music, playing, now):
        return {"kind": "playing", "stale": False, "present": False}
    return {
        "kind": "playing", "stale": bool(music.get("stale")), "present": True,
        "title": latin1(playing.get("title") or ""),
        "subtitle": latin1(playing.get("subtitle") or ""),
        "cover": _cover_path(playing.get("cover"), "big"),
        "colour": playing.get("colour") or "#7c6cf2",
        "playing": playing.get("state") == "playing",
        "progress_ms": playing.get("progress_ms") or 0,
        "duration_ms": playing.get("duration_ms") or 0,
        # When the progress was read: the panel moves the bar on from there.
        "at": round(music.get("as_of") or now.timestamp(), 3),
        "device": _device_name(playing.get("device"), music.get("default_device") or ""),
    }


def music_screen(music: dict[str, Any] | None) -> dict[str, Any]:
    """The cover wall (plan.md M27, M): the favourites, then the playlists and albums played
    lately, each a tap to play, over the colour of what plays (or played last)."""
    favourites = (music or {}).get("favourites") or []
    recent = (music or {}).get("recent") or []
    if not music or not music.get("connected") or not (favourites or recent):
        return {"kind": "music", "stale": False, "present": False}
    playing = music.get("playing") or {}
    last = playing or music.get("last") or {}
    line = " · ".join(p for p in (last.get("title"), last.get("subtitle")) if p)
    heading = "Now playing" if playing else "Last played"
    context = playing.get("context")
    if playing.get("title"):
        footer = f"{playing['title']} is playing · tap a cover to play it"
    elif last.get("title"):
        footer = f"Last played: {last['title']} · tap a cover to play it"
    else:
        footer = "Tap a cover to play it"
    return {
        "kind": "music", "stale": bool(music.get("stale")), "present": True,
        "device": _device_name(playing.get("device"), music.get("default_device") or ""),
        "favourites": [{"position": f["position"], "name": latin1(f["name"]),
                        "cover": _cover_path(f.get("cover"), "tile"),
                        "thumb": _cover_path(f.get("cover"), "thumb"),
                        "wall": _cover_path(f.get("cover"), "wall"),
                        "colour": f.get("colour") or "#7c6cf2",
                        "playing": context == f"spotify:playlist:{f.get('id')}"}
                       for f in favourites[:4]],
        "recent": [{"name": latin1(r["name"]), "wall": _cover_path(r.get("cover"), "wall"),
                    "colour": r.get("colour") or "#7c6cf2", "playing": context == r["uri"]}
                   for r in recent[:4]],
        # The wash behind the wall: the colour of what plays, or played last.
        "colour": last.get("colour") or "#7c6cf2",
        "footer": latin1(footer),
        # One line for the panels that still draw it; the list layout draws the parts.
        "last": latin1(f"{heading}: {line}") if line else "",
        "last_heading": heading if line else "",
        "last_title": latin1(last.get("title") or ""),
        "last_subtitle": latin1(last.get("subtitle") or ""),
        "last_cover": _cover_path(last.get("cover"), "thumb") if line else None,
    }


async def cover(store: Store, key: str, size: CoverSize) -> bytes | None:
    """A stored Spotify cover as a baseline JPEG at the panel's size, or None."""
    if (key, size) in _covers:
        _covers.move_to_end((key, size))
        return _covers[(key, size)]
    found = await spotify.cover(store, key, spotify.CLIENT.transport)
    if found is None:
        return None

    def make() -> bytes:
        with Image.open(io.BytesIO(found[0])) as image:
            fitted = ImageOps.fit(image.convert("RGB"), COVER_SIZES[size],
                                  Image.Resampling.LANCZOS)
        out = io.BytesIO()
        fitted.save(out, "JPEG", quality=85, progressive=False, subsampling="4:2:0")
        return out.getvalue()

    _covers[(key, size)] = await asyncio.to_thread(make)
    while len(_covers) > KEEP_COVERS:
        _covers.popitem(last=False)
    return _covers[(key, size)]


# --- laundry ---------------------------------------------------------------------------

MACHINE_COLOUR = {"washer": "#9c8ffb", "dryer": "#5aa9ff"}
STATE_COLOUR = {"done": "#3fb97f", "paused": "#e0a23b", "error": "#e5646a"}


def _machine(m: dict[str, Any], zone: ZoneInfo) -> dict[str, Any]:
    """One machine as the hub's laundry card shows it (web LaundryCard)."""
    def hm(at: str | None) -> str:
        return datetime.fromisoformat(at).astimezone(zone).strftime("%H:%M") if at else ""

    state, kind = m["state"], m["kind"]
    progress = 0.0
    if state == "done":
        progress = 1.0
    elif m.get("total_minutes") and m.get("remaining_minutes") is not None:
        progress = max(0.0, min(1.0, 1 - m["remaining_minutes"] / m["total_minutes"]))
    program = latin1(m.get("program") or "")
    lines = {
        "done": (f"Done at {hm(m.get('done_at'))}" if m.get("done_at") else "Done", "Take it out"),
        "paused": (program, "Paused"),
        "error": ("See the manual" if (m.get("error") or "").startswith("F") else program,
                  f"Error {m['error']}" if (m.get("error") or "").startswith("F")
                  else latin1(m.get("error") or "")),
        "running": (program,
                    f"Ready at {hm(m.get('ready_at'))}" if m.get("ready_at") else "Running"),
    }.get(state, ("", ""))
    return {
        "name": "Washer" if kind == "washer" else "Dryer", "state": state,
        "colour": STATE_COLOUR.get(state, MACHINE_COLOUR.get(kind, "#9c8ffb")),
        "water": MACHINE_COLOUR.get(kind, "#9c8ffb"),
        "progress": round(progress * 1000),
        "minutes": m.get("remaining_minutes") if state in ("running", "paused") else None,
        "line": lines[0], "status": lines[1],
        "status_colour": STATE_COLOUR.get(state, MACHINE_COLOUR.get(kind, "#9c8ffb")),
    }


def _headline(machines: list[dict[str, Any]]) -> tuple[str, str]:
    states = [m["state"] for m in machines]
    if "error" in states:
        return "Needs a look", STATE_COLOUR["error"]
    if "done" in states:
        return "Done", STATE_COLOUR["done"]
    if "paused" in states:
        return "Paused", STATE_COLOUR["paused"]
    running = [m for m in machines if m["state"] == "running"]
    if len(running) > 1:
        return "Both running", "#b4a9ff"
    return ("Dryer running" if running and running[0]["kind"] == "dryer" else "Washer running",
            "#b4a9ff")


def laundry_screen(store: Store, zone: ZoneInfo, now: datetime) -> dict[str, Any]:
    """The washer and dryer, only while one runs, is paused, has an error or is done."""
    cached = store.get_cache(laundry.CACHE_KEY)
    if not cached or not cached.get("showing"):
        return {"kind": "laundry", "stale": False, "present": False}
    machines = cached.get("machines") or []
    word, colour = _headline(machines)
    return {"kind": "laundry", "stale": bool(cached.get("stale")), "present": True,
            "headline": word, "headline_colour": colour,
            "machines": [_machine(m, zone) for m in machines[:2]]}


# --- Air ---------------------------------------------------------------------------------

AIR_WORDS = {"fresh": ("Fresh", "#3fb97f"), "stuffy": ("Getting stuffy", "#e0a23b"),
             "open_window": ("Open a window", "#e5646a")}
RING_LOW, RING_HIGH = 400, 2000  # ppm over the ring's three quarters, as in the hub


def air_screen(store: Store, zone: ZoneInfo, now: datetime) -> dict[str, Any]:
    """The living room's air: the temperature large, humidity, fine dust and the sensor's
    verdict, CO2 as a ring with its word, and CO2 over the last 8 hours (plan.md M17)."""
    cached = store.get_cache(air.CACHE_KEY)
    if not cached or (cached.get("temperature") is None and cached.get("co2") is None):
        return {"kind": "air", "stale": False, "present": False}
    temperature, co2, outside = cached.get("temperature"), cached.get("co2"), cached.get("outside")
    word, colour = AIR_WORDS.get(cached.get("level") or "", ("", "#8a8794"))
    share = 0.0
    if co2 is not None:
        share = (min(max(co2, RING_LOW), RING_HIGH) - RING_LOW) / (RING_HIGH - RING_LOW)
    return {
        "kind": "air", "stale": bool(cached.get("stale")) or not cached.get("available", True),
        "present": True,
        "room": latin1(cached.get("room") or "Living room"),
        "outside": f"Outside {outside}°" if outside is not None else "",
        # A comma: the panel's large-number font has no point (fonts/make-fonts.sh).
        "temperature": f"{temperature:.1f}°".replace(".", ",") if temperature is not None else "",
        "humidity": f"{cached['humidity']}%" if cached.get("humidity") is not None else "",
        "pm25": str(cached["pm25"]) if cached.get("pm25") is not None else "",
        "quality": latin1(cached.get("quality") or ""),
        "co2": co2, "ring": round(share * 1000), "word": word, "colour": colour,
        # CO2 every 5 minutes over the last 8 hours, for the curve.
        "history": [p["co2"] for p in cached.get("history") or []][-97:],
    }


# --- Apple devices ---------------------------------------------------------------------

PLAYS_COLOUR = {"video": "#5aa9ff", "music": "#9c8ffb"}  # a room's glow while something plays


def _plays(room: dict[str, Any], device: dict[str, Any]) -> bool:
    """Whether a device sends out ripples, as on the hub's card: the room's HomePods (a
    stereo pair plays as one) and, for video or when it is the one playing, its Apple TV."""
    playing = room.get("playing") or {}
    if playing.get("state") != "playing" or not device.get("online"):
        return False
    return (device.get("kind") != "tv" or playing.get("media") == "video"
            or device.get("id") == playing.get("device"))


def apple_screen(store: Store, zone: ZoneInfo, now: datetime) -> dict[str, Any]:
    """The Apple TVs and HomePods as a map of the house: rooms that glow with
    what plays in them, each device online or not, and what plays."""
    cached = store.get_cache(apple.CACHE_KEY)
    if not cached or not cached.get("rooms"):
        return {"kind": "apple", "stale": False, "present": False}
    rooms = cached["rooms"][:3]
    offline = sum(1 for r in rooms for d in r.get("devices") or [] if not d.get("online"))
    playing = next(((r, r["playing"]) for r in rooms if r.get("playing")), None)
    return {
        "kind": "apple", "stale": bool(cached.get("stale")), "present": True,
        "headline": f"{offline} offline" if offline else "All online",
        "headline_colour": "#e0a23b" if offline else "#3fb97f",
        "rooms": [{"name": latin1(r["name"]),
                   "glow": PLAYS_COLOUR.get((r.get("playing") or {}).get("media") or "")
                   if r.get("playing") and r["playing"].get("state") == "playing" else None,
                   "devices": [{"kind": d.get("kind") or "homepod", "online": bool(d.get("online")),
                                # The Thread mesh (2026-10-23): border routers, and whether
                                # Thread is up on them; the panel draws the links.
                                "router": d.get("thread") is not None,
                                "thread_ok": bool(d.get("online")) and d.get("thread") is True,
                                "plays": _plays(r, d)}
                               for d in (r.get("devices") or [])[:4]]} for r in rooms],
        "playing": None if playing is None else {
            "title": latin1(" · ".join(p for p in (playing[1].get("title"),
                                                   playing[1].get("subtitle")) if p)),
            "where": latin1(f"{playing[0]['name']} · "
                            f"{'playing' if playing[1].get('state') == 'playing' else 'paused'}"
                            + (f" · {playing[1]['app']}" if playing[1].get("app") else "")),
            "colour": PLAYS_COLOUR.get(playing[1].get("media") or "", "#9c8ffb"),
        },
    }
