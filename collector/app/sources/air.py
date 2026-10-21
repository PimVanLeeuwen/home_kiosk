"""The living room's air (plan.md M17), for the Air card on Home and the Home panel.

The IKEA ALPSTUGA is a Matter-over-Thread sensor in Apple Home; the Matter server
on the NAS (nas-docker `matter` stack, the OHF matter.js server) is its second
controller and keeps it subscribed. The hub only asks that server for the node
over its WebSocket API (`get_node`, read-only) and reads the standard clusters:
temperature and humidity in hundredths, CO2 in ppm, PM2.5 in µg/m³, and the
sensor's own air quality verdict. A CO2 sample every 5 minutes, kept for a day,
draws the last 8 hours.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from typing import Any, Literal, Protocol

import websockets

from ..models import AirPoint, AirState
from ..store import Store

log = logging.getLogger(__name__)

CACHE_KEY = "air"
TIMEOUT_SECONDS = 15

# Matter cluster ids (attribute 0 is the measured value).
TEMPERATURE, HUMIDITY, CO2, PM25, AIR_QUALITY = 1026, 1029, 1037, 1066, 91
QUALITY = {1: "Good", 2: "Fair", 3: "Moderate", 4: "Poor", 5: "Very poor", 6: "Extremely poor"}

# The CO2 ring's words (plan.md M17), ppm.
STUFFY_FROM, OPEN_FROM = 800, 1200

SAMPLE_EVERY = timedelta(minutes=5)
KEEP = timedelta(hours=24)
SHOWN = timedelta(hours=8)

TABLES = """
CREATE TABLE IF NOT EXISTS air_sample (
    at   TEXT PRIMARY KEY,  -- UTC, ISO
    co2  REAL NOT NULL
);
"""


class Socket(Protocol):
    async def send(self, message: str) -> None: ...
    async def recv(self) -> str | bytes: ...


Connect = Callable[[str], Awaitable[Any]]  # an async context manager yielding a Socket


def settings(cfg: dict[str, Any]) -> dict[str, Any]:
    a = cfg.get("air") or {}
    url = str(a.get("matter") or "").strip()
    node = a.get("node")
    return {"url": url, "node": int(node) if node is not None else None,
            "room": str(a.get("room") or "Living room"),
            "enabled": bool(url and node is not None)}


def ensure_tables(store: Store) -> None:
    with store.connect() as conn:
        conn.executescript(TABLES)


def level(co2: float | None) -> Literal["fresh", "stuffy", "open_window"] | None:
    if co2 is None:
        return None
    return "fresh" if co2 < STUFFY_FROM else "stuffy" if co2 <= OPEN_FROM else "open_window"


def _measured(attributes: dict[str, Any], cluster: int) -> Any:
    """Attribute 0 of the cluster, on whichever endpoint has it."""
    for key, value in attributes.items():
        _, found, attribute = key.split("/")
        if int(found) == cluster and int(attribute) == 0 and value is not None:
            return value
    return None


def readings(node: dict[str, Any]) -> dict[str, Any]:
    """The node's values, rounded the way the card shows them."""
    attrs = node.get("attributes") or {}
    temperature, humidity = _measured(attrs, TEMPERATURE), _measured(attrs, HUMIDITY)
    co2, pm25 = _measured(attrs, CO2), _measured(attrs, PM25)
    quality = _measured(attrs, AIR_QUALITY)
    return {
        "temperature": round(temperature / 100, 1) if temperature is not None else None,
        "humidity": round(humidity / 100) if humidity is not None else None,
        "co2": round(co2) if co2 is not None else None,
        "pm25": round(pm25) if pm25 is not None else None,
        "quality": QUALITY.get(quality) if quality is not None else None,
    }


async def _command(ws: Socket, command: str, args: dict[str, Any]) -> Any:
    """Send one command and wait for its answer (other messages are skipped)."""
    await ws.send(json.dumps({"message_id": command, "command": command, "args": args}))
    while True:
        message = json.loads(await ws.recv())
        if message.get("message_id") != command:
            continue
        if "error_code" in message:
            raise RuntimeError(f"Matter server: {message.get('details') or message['error_code']}")
        return message.get("result")


async def read_node(url: str, node_id: int, connect: Connect | None = None) -> dict[str, Any]:
    opener = connect or (lambda u: websockets.connect(u, open_timeout=TIMEOUT_SECONDS,
                                                      close_timeout=2))
    async with opener(url) as ws:
        await ws.recv()  # the server's own info comes first
        node = await _command(ws, "get_node", {"node_id": node_id})
    if not isinstance(node, dict):
        raise RuntimeError(f"Matter server: no node {node_id}")
    return node


def _sample(store: Store, now: datetime, co2: float | None) -> list[AirPoint]:
    """Keep a CO2 sample every SAMPLE_EVERY and answer with the last SHOWN of them."""
    with store.connect() as conn:
        last = conn.execute("SELECT MAX(at) AS at FROM air_sample").fetchone()["at"]
        if co2 is not None and (last is None or now - datetime.fromisoformat(last) >= SAMPLE_EVERY):
            conn.execute("INSERT OR REPLACE INTO air_sample (at, co2) VALUES (?, ?)",
                         (now.isoformat(), co2))
        conn.execute("DELETE FROM air_sample WHERE at < ?", ((now - KEEP).isoformat(),))
        rows = conn.execute("SELECT at, co2 FROM air_sample WHERE at >= ? ORDER BY at",
                            ((now - SHOWN).isoformat(),)).fetchall()
    return [AirPoint(at=datetime.fromisoformat(r["at"]), co2=round(r["co2"])) for r in rows]


async def collect(cfg: dict[str, Any], store: Store, connect: Connect | None = None,
                  now: datetime | None = None) -> AirState:
    """`connect` and `now` are for tests."""
    a = settings(cfg)
    now = now or datetime.now(UTC)
    node = await read_node(a["url"], a["node"], connect)
    values = readings(node)
    outside = (store.get_cache("weather") or {}).get("temperature")
    return AirState(
        as_of=now, room=a["room"], available=bool(node.get("available", True)), **values,
        level=level(values["co2"]),
        outside=round(outside) if isinstance(outside, (int, float)) else None,
        history=_sample(store, now, values["co2"]),
    )
