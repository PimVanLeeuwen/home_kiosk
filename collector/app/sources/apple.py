"""Apple devices: the Apple TVs and HomePods, online, Thread and what plays.

Every device is asked directly at its reserved address (unicast DNS-SD), so
the collector needs no multicast and stays on its bridge network:
`_airplay` says it is up and which model it is, and `_meshcop` that
it is a Thread border router and whether its Thread interface is active.

What plays comes from pyatv (MIT). HomePods tell it without pairing; the
living room's pair reports what its Apple TV plays, since they are its
speakers. An Apple TV needs AirPlay credentials (a one-time PIN pairing) and
is otherwise not asked. Read-only: nothing is ever sent to play or pause.
"""

from __future__ import annotations

import asyncio
import hashlib
import io
import logging
import re
from datetime import UTC, datetime
from typing import Any, Literal, Protocol

from PIL import Image, ImageOps
from pydantic import BaseModel

from ..models import Envelope
from ..store import Store

log = logging.getLogger(__name__)

CACHE_KEY = "apple"
QUERY_TIMEOUT = 2  # seconds; a device that is up answers within milliseconds
READ_TIMEOUT = 10
ARTWORK_SIZE = 200

Kind = Literal["tv", "homepod", "homepod_mini"]
Media = Literal["video", "music", "other"]

TABLES = """
-- The artwork of what plays in a room, kept until something else plays there.
CREATE TABLE IF NOT EXISTS apple_artwork (
    room  TEXT PRIMARY KEY,
    key   TEXT NOT NULL,  -- what played when it was fetched
    image BLOB            -- NULL: that item has none
);
"""

_SERVICES = ["_airplay._tcp.local", "_meshcop._udp.local"]


class AppleDevice(BaseModel):
    id: str
    name: str
    kind: Kind | None = None  # None until it has answered once
    online: bool
    offline_since: datetime | None = None
    # None: not a Thread border router; else whether its Thread interface is active.
    thread: bool | None = None


class Playing(BaseModel):
    state: Literal["playing", "paused"]
    media: Media
    title: str
    subtitle: str | None = None
    app: str | None = None
    device: str  # the id of the device that reported it
    artwork: bool = False


class AppleRoom(BaseModel):
    id: str
    name: str
    devices: list[AppleDevice]
    playing: Playing | None = None


class AppleDevices(Envelope):
    rooms: list[AppleRoom]


# --- what a device says -------------------------------------------------------------


class Answer(BaseModel):
    """One device's answer to the unicast query."""

    model: str | None = None
    airplay: bool = False
    border_router: bool = False
    thread_active: bool = False


class Reading(BaseModel):
    """What one device reports playing."""

    state: Literal["playing", "paused", "idle"]
    media: Media = "other"
    title: str | None = None
    subtitle: str | None = None
    app: str | None = None


class Probe(Protocol):
    async def ask(self, address: str) -> Answer | None: ...
    async def read(self, address: str, credentials: str | None) -> Reading | None: ...
    async def artwork(self, address: str, credentials: str | None) -> bytes | None: ...


def slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def kind_of(model: str | None) -> Kind | None:
    """AppleTV14,1 is an Apple TV; AudioAccessory5 the HomePod mini; 1 and 6 the HomePod."""
    if not model:
        return None
    if model.startswith("AppleTV"):
        return "tv"
    if model.startswith("AudioAccessory5"):
        return "homepod_mini"
    if model.startswith("AudioAccessory"):
        return "homepod"
    return None


def thread_active(state_bitmap: str | bytes | None) -> bool:
    """The `sb` TXT value of a border router: bits 3 and 4 are the Thread
    interface status, 2 meaning initialised and active."""
    if not state_bitmap:
        return False
    raw = state_bitmap if isinstance(state_bitmap, bytes) else None
    if raw is None:
        # pyatv hands TXT values over as text, binary ones as "b'\\x00...'".
        text = str(state_bitmap)
        if text.startswith(("b'", 'b"')):
            raw = bytes(text[2:-1], "latin-1").decode("unicode_escape").encode("latin-1")
        else:
            raw = text.encode("latin-1")
    value = int.from_bytes(raw, "big")
    return (value >> 3) & 0b11 == 2


def subtitle_of(playing: Any) -> str | None:
    series, season, episode = playing.series_name, playing.season_number, playing.episode_number
    if season and episode:
        prefix = f"S{season} E{episode}"
        return f"{prefix} · {series}" if series and series != playing.title else prefix
    parts = [p for p in (playing.artist, playing.album) if p]
    return " · ".join(parts) or None


class PyatvProbe:
    """The real thing: pyatv's unicast DNS-SD and its metadata."""

    async def ask(self, address: str) -> Answer | None:
        from pyatv.core import mdns

        loop = asyncio.get_running_loop()
        response = await mdns.unicast(loop, address, _SERVICES, timeout=QUERY_TIMEOUT)
        if not response.services:
            return None
        answer = Answer()
        for service in response.services:
            # _device-info's model is a board code (B520AP); AirPlay's names the product.
            if service.type == "_airplay._tcp.local":
                answer.airplay = True
                answer.model = service.properties.get("model")
            elif service.type == "_meshcop._udp.local":
                answer.border_router = True
                answer.thread_active = thread_active(service.properties.get("sb"))
        return answer

    async def _connect(self, address: str, credentials: str | None) -> Any:
        import pyatv
        from pyatv.const import Protocol as AtvProtocol

        loop = asyncio.get_running_loop()
        found = await pyatv.scan(loop, hosts=[address], timeout=QUERY_TIMEOUT)
        if not found:
            return None
        conf = found[0]
        if credentials:
            conf.set_credentials(AtvProtocol.AirPlay, credentials)
        return await pyatv.connect(conf, loop)

    async def artwork(self, address: str, credentials: str | None) -> bytes | None:
        atv = await self._connect(address, credentials)
        if atv is None:
            return None
        try:
            art = await atv.metadata.artwork(width=ARTWORK_SIZE * 2)
            return art.bytes if art else None
        finally:
            atv.close()

    async def read(self, address: str, credentials: str | None) -> Reading | None:
        from pyatv.const import DeviceState, MediaType

        atv = await self._connect(address, credentials)
        if atv is None:
            return None
        try:
            playing = await atv.metadata.playing()
            state = {DeviceState.Playing: "playing", DeviceState.Paused: "paused"}.get(
                playing.device_state, "idle")
            if state == "idle" or not playing.title:
                return Reading(state="idle")
            try:
                app = atv.metadata.app.name if atv.metadata.app else None
            except Exception:
                app = None
            media = {MediaType.Video: "video", MediaType.TV: "video",
                     MediaType.Music: "music"}.get(playing.media_type, "other")
            return Reading(state=state, media=media, title=playing.title,
                           subtitle=subtitle_of(playing), app=app)
        finally:
            atv.close()


# --- the house ----------------------------------------------------------------------


def ensure_tables(store: Store) -> None:
    with store.connect() as conn:
        conn.executescript(TABLES)


def settings(cfg: dict[str, Any]) -> dict[str, Any]:
    rooms = (cfg.get("apple") or {}).get("rooms") or []
    return {"enabled": any(r.get("devices") for r in rooms), "rooms": rooms}


def shrink(data: bytes) -> bytes:
    with Image.open(io.BytesIO(data)) as raw:
        picture = ImageOps.exif_transpose(raw).convert("RGB")
    out = io.BytesIO()
    ImageOps.fit(picture, (ARTWORK_SIZE, ARTWORK_SIZE), Image.Resampling.LANCZOS).save(
        out, "WEBP", quality=80)
    return out.getvalue()


def artwork(store: Store, room: str) -> bytes | None:
    with store.connect() as conn:
        row = conn.execute("SELECT image FROM apple_artwork WHERE room = ?", (room,)).fetchone()
    return row[0] if row else None


def _known_artwork(store: Store, room: str) -> tuple[str, bool] | None:
    with store.connect() as conn:
        row = conn.execute("SELECT key, image IS NOT NULL FROM apple_artwork WHERE room = ?",
                           (room,)).fetchone()
    return (row[0], bool(row[1])) if row else None


def _keep_artwork(store: Store, room: str, key: str, data: bytes | None) -> bool:
    image = None
    if data:
        try:
            image = shrink(data)
        except Exception as exc:
            log.info("unreadable artwork in %s: %s", room, type(exc).__name__)
    with store.connect() as conn:
        conn.execute("INSERT OR REPLACE INTO apple_artwork (room, key, image) VALUES (?, ?, ?)",
                     (room, key, image))
    return image is not None


def _credentials(dev: dict[str, Any]) -> str | None:
    return (dev.get("credentials") or "").strip() or None


async def _safe(coro: Any, timeout: float) -> Any:
    try:
        return await asyncio.wait_for(coro, timeout)
    except Exception as exc:
        log.info("apple device did not answer: %s", type(exc).__name__)
        return None


async def collect(cfg: dict[str, Any], store: Store, probe: Probe | None = None,
                  now: datetime | None = None) -> AppleDevices:
    probe = probe or PyatvProbe()
    now = now or datetime.now(UTC)
    rooms_cfg = settings(cfg)["rooms"]
    before = {d["id"]: d for room in (store.get_cache(CACHE_KEY) or {}).get("rooms") or []
              for d in room.get("devices") or []}

    devices = [(room, dev) for room in rooms_cfg for dev in room.get("devices") or []]
    answers = await asyncio.gather(*(
        _safe(probe.ask(str(dev["address"])), QUERY_TIMEOUT + 2) for _, dev in devices))

    rooms: list[AppleRoom] = []
    for room in rooms_cfg:
        room_id = slug(room["name"])
        listed = []
        for (r, dev), answer in zip(devices, answers, strict=True):
            if r is not room:
                continue
            dev_id = slug(dev["name"])
            last = before.get(dev_id) or {}
            online = answer is not None
            listed.append((dev, answer, AppleDevice(
                id=dev_id, name=dev["name"],
                kind=kind_of(answer.model) if answer else last.get("kind"),
                online=online,
                offline_since=None if online else (last.get("offline_since") or now),
                thread=(answer.thread_active if answer.border_router else None) if answer
                else last.get("thread"),
            )))

        # Who to ask what plays: HomePods, and Apple TVs that have been paired.
        askable = [(dev, d) for dev, answer, d in listed
                   if answer and (d.kind != "tv" or _credentials(dev))]
        known = _known_artwork(store, room_id)
        readings = await asyncio.gather(*(
            _safe(probe.read(str(dev["address"]), _credentials(dev)), READ_TIMEOUT)
            for dev, _ in askable))
        found = [(dev, d, r) for (dev, d), r in zip(askable, readings, strict=True)
                 if r and r.state != "idle"]
        pick = next((x for x in found if x[2].state == "playing"), found[0] if found else None)

        playing = None
        if pick:
            dev, device, reading = pick
            key = hashlib.sha256(f"{reading.title}|{reading.subtitle}".encode()).hexdigest()[:16]
            if known and known[0] == key:
                has_art = known[1]
            else:
                # Fetched once per item: when something new starts playing in the room.
                data = await _safe(probe.artwork(str(dev["address"]), _credentials(dev)),
                                   READ_TIMEOUT)
                has_art = _keep_artwork(store, room_id, key, data)
            playing = Playing(state=reading.state, media=reading.media, title=reading.title or "",
                              subtitle=reading.subtitle, app=reading.app, device=device.id,
                              artwork=has_art)
        rooms.append(AppleRoom(id=room_id, name=room["name"],
                               devices=[d for _, _, d in listed], playing=playing))
    return AppleDevices(as_of=now, stale=False, rooms=rooms)
