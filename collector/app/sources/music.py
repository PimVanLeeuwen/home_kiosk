"""The Music page's answer and actions, on top of the Spotify client.

A favourite starts on the device that is already playing; when nothing plays,
on the living room Apple TV (config `music.default_device`). The Apple TV is
only a Spotify device while its Spotify app is open, so `wake` (set up by the
Apple TV step, M18) may switch it on and open the app first.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from typing import Any

from ..store import Store
from . import spotify
from .spotify import CLIENT, SpotifyError

# How long to wait for a woken Apple TV to show up in Spotify.
WAKE_WAIT_SECONDS = 15
WAKE_POLL_SECONDS = 1.5

# Set by the Apple TV step: switches the TV on and opens Spotify; returns
# whether it tried. None: the hub cannot wake it.
wake: Callable[[dict[str, Any]], Awaitable[bool]] | None = None


def _cover_url(images: list[dict[str, Any]] | None) -> str | None:
    """The smallest image at least 300 px wide, else the largest."""
    images = sorted(images or [], key=lambda i: i.get("width") or 0)
    if not images:
        return None
    return next((i["url"] for i in images if (i.get("width") or 0) >= 300), images[-1]["url"])


def _device(d: dict[str, Any]) -> dict[str, Any]:
    return {"id": d.get("id"), "name": d.get("name") or "Unknown device",
            "type": (d.get("type") or "").lower(), "active": bool(d.get("is_active")),
            "volume": d.get("volume_percent"),
            "restricted": bool(d.get("is_restricted"))}


async def _item(store: Store, item: dict[str, Any]) -> dict[str, Any]:
    """Title, subtitle and cover of a track or an episode."""
    if item.get("type") == "episode":
        show = item.get("show") or {}
        subtitle, kind = show.get("name"), "episode"
        images = item.get("images") or show.get("images")
    else:
        artists = ", ".join(a.get("name", "") for a in item.get("artists") or [])
        album = (item.get("album") or {})
        subtitle = " · ".join(p for p in (artists, album.get("name")) if p) or None
        images, kind = album.get("images"), "track"
    key = spotify.remember_cover(store, _cover_url(images))
    return {"kind": kind, "title": item.get("name") or "", "subtitle": subtitle,
            "duration_ms": item.get("duration_ms") or 0, "cover": key,
            "colour": await spotify.colour_of(store, key, CLIENT.transport)}


async def state(cfg: dict[str, Any], store: Store) -> dict[str, Any]:
    """What plays, the devices, the favourites and, when nothing plays, what played last."""
    base = {"as_of": time.time(), "stale": False, "connected": spotify.connected(store),
            "default_device": spotify.settings(cfg)["default_label"],
            "playing": None, "devices": [], "favourites": favourites(store), "last": None}
    if not base["connected"]:
        return base
    player = await CLIENT.cached(cfg, store, "player", "/me/player",
                                 {"additional_types": "episode"})
    devices = await CLIENT.cached(cfg, store, "devices", "/me/player/devices")
    base["devices"] = [_device(d) for d in (devices or {}).get("devices") or []]
    s = spotify.settings(cfg)
    # Learns its id; that device then goes by its own name ("Apple TV Living Room").
    known = pick(store, base["devices"], s["default_device"])
    for d in base["devices"]:
        if known and d["id"] == known:
            d["name"] = s["default_label"]
    if player and player.get("item"):
        base["playing"] = await _item(store, player["item"]) | {
            "state": "playing" if player.get("is_playing") else "paused",
            "progress_ms": player.get("progress_ms") or 0,
            "device": _device(player["device"]) if player.get("device") else None,
        }
        device = base["playing"]["device"]
        if known and device and device["id"] == known:
            device["name"] = s["default_label"]
    else:
        recent = await CLIENT.cached(cfg, store, "recent", "/me/player/recently-played",
                                     {"limit": 1})
        items = (recent or {}).get("items") or []
        if items and items[0].get("track"):
            base["last"] = await _item(store, items[0]["track"])
    for fav in base["favourites"]:
        fav["colour"] = await spotify.colour_of(store, fav["cover"], CLIENT.transport)
    return base


# The last state Spotify gave, for when it fails or asks the hub to slow down;
# kept in the database as well (at most every SAVE_EVERY seconds), so a restart
# while Spotify pauses the hub still has something to show.
LAST: dict[str, Any] = {}
LAST_KEY = "music_last"
SAVE_EVERY = 30.0
_saved_at = [0.0]


async def latest(cfg: dict[str, Any], store: Store) -> dict[str, Any]:
    """state(), or the last good one marked stale while Spotify fails or rate-limits
    the hub. While Spotify pauses the hub, `paused_until` says until when (epoch
    seconds) and, without any last answer, the favourites still show. Raises when
    there is nothing to show, or when the hub was disconnected (401)."""
    try:
        answer = await state(cfg, store)
    except Exception as exc:
        if isinstance(exc, SpotifyError) and exc.status == 401:
            raise
        paused = CLIENT.pause_end(store)
        last = LAST or store.get_cache(LAST_KEY)
        if last:
            return last | {"stale": True, "paused_until": paused}
        if paused is None:
            raise
        return await _waiting(cfg, store, paused)
    answer["paused_until"] = None
    LAST.clear()
    LAST.update(answer)
    if time.monotonic() - _saved_at[0] >= SAVE_EVERY or not _saved_at[0]:
        store.put_cache(LAST_KEY, answer)
        _saved_at[0] = time.monotonic()
    return answer


def forget(store: Store) -> None:
    """After disconnecting: no last answer to fall back on."""
    LAST.clear()
    store.put_cache(LAST_KEY, {})
    _saved_at[0] = 0.0


async def _waiting(cfg: dict[str, Any], store: Store, paused: float) -> dict[str, Any]:
    """No last answer while Spotify pauses the hub: what the hub knows itself."""
    favs = favourites(store)
    for fav in favs:
        fav["colour"] = await spotify.colour_of(store, fav["cover"], CLIENT.transport)
    return {"as_of": time.time(), "stale": True, "connected": spotify.connected(store),
            "default_device": spotify.settings(cfg)["default_label"], "playing": None,
            "devices": [], "favourites": favs, "last": None, "paused_until": paused}


# --- favourites ----------------------------------------------------------------------


def favourites(store: Store) -> list[dict[str, Any]]:
    with store.connect() as conn:
        rows = conn.execute("SELECT position, id, name, cover FROM music_favourite "
                            "ORDER BY position").fetchall()
    return [dict(r) | {"colour": None} for r in rows]


async def playlists(cfg: dict[str, Any], store: Store) -> list[dict[str, Any]]:
    """The account's own and followed playlists, for choosing favourites."""
    found, offset = [], 0
    while offset < 200:
        page = await CLIENT.call(cfg, store, "GET", "/me/playlists",
                                 {"limit": 50, "offset": offset})
        for p in (page or {}).get("items") or []:
            if p and p.get("id"):
                found.append({"id": p["id"], "name": p.get("name") or "Untitled",
                              "cover": spotify.remember_cover(store, _cover_url(p.get("images"))),
                              "owner": (p.get("owner") or {}).get("display_name")})
        if not (page or {}).get("next"):
            break
        offset += 50
    return found


async def set_favourites(cfg: dict[str, Any], store: Store, ids: list[str]) -> list[dict]:
    if len(ids) > spotify.FAVOURITES or len(set(ids)) != len(ids):
        raise SpotifyError(f"Choose up to {spotify.FAVOURITES} different playlists.", 422)
    known = {p["id"]: p for p in await playlists(cfg, store)}
    missing = [i for i in ids if i not in known]
    if missing:
        raise SpotifyError("That playlist is not in your Spotify library.", 422)
    with store.connect() as conn:
        conn.execute("DELETE FROM music_favourite")
        conn.executemany(
            "INSERT INTO music_favourite (position, id, name, cover) VALUES (?, ?, ?, ?)",
            [(n, i, known[i]["name"], known[i]["cover"]) for n, i in enumerate(ids)])
    return favourites(store)


# --- actions -------------------------------------------------------------------------


async def control(cfg: dict[str, Any], store: Store, action: str) -> None:
    method, path = {"play": ("PUT", "/me/player/play"), "pause": ("PUT", "/me/player/pause"),
                    "next": ("POST", "/me/player/next"),
                    "previous": ("POST", "/me/player/previous")}[action]
    await CLIENT.call(cfg, store, method, path)
    CLIENT.changed()


async def volume(cfg: dict[str, Any], store: Store, percent: int) -> None:
    await CLIENT.call(cfg, store, "PUT", "/me/player/volume", {"volume_percent": percent})
    CLIENT.changed()


async def transfer(cfg: dict[str, Any], store: Store, device_id: str) -> None:
    await CLIENT.call(cfg, store, "PUT", "/me/player", body={"device_ids": [device_id],
                                                              "play": True})
    CLIENT.changed()


async def _devices(cfg: dict[str, Any], store: Store) -> list[dict[str, Any]]:
    CLIENT.cache.pop("devices", None)
    answer = await CLIENT.cached(cfg, store, "devices", "/me/player/devices")
    return [_device(d) for d in (answer or {}).get("devices") or []]


def pick(store: Store, devices: list[dict[str, Any]], name: str) -> str | None:
    """The default device among those listed. Spotify names every Apple TV the
    same, so its id is remembered while only one is listed, and preferred when
    several are."""
    matches = [d["id"] for d in devices if d["name"] == name and d["id"]]
    with store.connect() as conn:
        if len(matches) == 1:
            conn.execute("INSERT INTO music_device (name, id) VALUES (?, ?) ON CONFLICT(name) "
                         "DO UPDATE SET id = excluded.id", (name, matches[0]))
            return matches[0]
        row = conn.execute("SELECT id FROM music_device WHERE name = ?", (name,)).fetchone()
    return row["id"] if row and row["id"] in matches else None


async def target(cfg: dict[str, Any], store: Store,
                 sleep: Callable[[float], Awaitable[Any]] = asyncio.sleep) -> str:
    """The device a favourite starts on: the one playing now, else the Apple TV,
    woken and with Spotify opened when it is not listed yet."""
    CLIENT.cache.pop("player", None)
    player = await CLIENT.cached(cfg, store, "player", "/me/player",
                                 {"additional_types": "episode"})
    if player and player.get("is_playing") and (player.get("device") or {}).get("id"):
        return player["device"]["id"]
    s = spotify.settings(cfg)
    name, label = s["default_device"], s["default_label"]
    found = pick(store, await _devices(cfg, store), name)
    if found:
        return found
    if wake is None or not await wake(cfg):
        raise SpotifyError(f"{label} is not available in Spotify: open Spotify on it first.", 409)
    waited = 0.0
    while waited < WAKE_WAIT_SECONDS:
        await sleep(WAKE_POLL_SECONDS)
        waited += WAKE_POLL_SECONDS
        found = pick(store, await _devices(cfg, store), name)
        if found:
            return found
    raise SpotifyError(f"{label} did not show up in Spotify; is it on?", 504)


async def play_favourite(cfg: dict[str, Any], store: Store, position: int,
                         sleep: Callable[[float], Awaitable[Any]] = asyncio.sleep) -> str:
    fav = next((f for f in favourites(store) if f["position"] == position), None)
    if fav is None:
        raise SpotifyError("No such favourite.", 404)
    device = await target(cfg, store, sleep)
    await CLIENT.call(cfg, store, "PUT", "/me/player/play", {"device_id": device},
                      {"context_uri": f"spotify:playlist:{fav['id']}"})
    CLIENT.changed()
    return device
