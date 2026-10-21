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
from .sources import apple, hue, laundry, spotify
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
COVER_SIZES = {"big": (288, 288), "tile": (320, 256)}  # multiples of 16, for the decoder
_covers: OrderedDict[tuple[str, str], bytes] = OrderedDict()
KEEP_COVERS = 16


def _cover_path(key: str | None, size: str) -> str | None:
    return f"/api/desk/cover/{key}/{size}" if key else None


def _device_name(device: dict[str, Any] | None, fallback: str) -> str:
    return latin1((device or {}).get("name") or fallback)


def playing_screen(music: dict[str, Any] | None, now: datetime) -> dict[str, Any]:
    """Now Playing: shown first on the Home panel while something plays or is paused."""
    playing = (music or {}).get("playing")
    if not playing:
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
    """The favourites to start, while Spotify is connected and some are chosen."""
    if not music or not music.get("connected") or not music.get("favourites"):
        return {"kind": "music", "stale": False, "present": False}
    playing = music.get("playing") or {}
    last = playing or music.get("last") or {}
    line = " · ".join(p for p in (last.get("title"), last.get("subtitle")) if p)
    return {
        "kind": "music", "stale": bool(music.get("stale")), "present": True,
        "device": _device_name(playing.get("device"), music.get("default_device") or ""),
        "favourites": [{"position": f["position"], "name": latin1(f["name"]),
                        "cover": _cover_path(f.get("cover"), "tile"),
                        "colour": f.get("colour") or "#7c6cf2"}
                       for f in music["favourites"][:4]],
        "last": latin1(("Now playing: " if playing else "Last played: ") + line) if line else "",
    }


async def cover(store: Store, key: str, size: Literal["big", "tile"]) -> bytes | None:
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


# --- Apple devices ---------------------------------------------------------------------

PLAYS_COLOUR = {"video": "#5aa9ff", "music": "#9c8ffb"}  # a room's glow while something plays


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
                   "devices": [{"kind": d.get("kind") or "homepod", "online": bool(d.get("online"))}
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
