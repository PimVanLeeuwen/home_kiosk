"""The panels' painted backgrounds (plan.md M27): the hub paints a screen's rich layer
(light, clouds, glow, grain) as a 720 x 720 JPEG; the panel shows it under its live
text, decoded by the P4's JPEG engine.

A screen with a painter gets `background`: a path with a key made from what the
picture shows, so a panel fetches it only when that changes. The answer only notes
the key and its inputs; the picture is painted on the panel's first request (as
covers are fetched on first use) and kept, the newest few per screen kind.
"""

from __future__ import annotations

import hashlib
import json
import weakref
from collections.abc import Callable
from datetime import datetime
from typing import Any

from PIL import Image

from . import (
    paint,
    paint_agenda,
    paint_air,
    paint_apple,
    paint_clock,
    paint_day,
    paint_headlines,
    paint_laundry,
    paint_playing,
)
from .store import Store

# Bumped when a painter changes, so every background is painted again.
VERSION = 4
KEEP = 6  # per kind: what the panels may still ask for
PATH = "/api/desk/background/"

TABLES = """
CREATE TABLE IF NOT EXISTS desk_background (
    key     TEXT PRIMARY KEY,
    kind    TEXT NOT NULL,
    inputs  TEXT NOT NULL,
    jpeg    BLOB,
    made_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS desk_background_kind ON desk_background (kind, made_at);
"""

Inputs = Callable[[dict[str, Any], datetime], dict[str, Any] | None]
# A painter gets its inputs and the store (for pictures the hub keeps); None: nothing to paint.
Painter = Callable[[dict[str, Any], Store], Image.Image | None]
PAINTERS: dict[str, tuple[Inputs, Painter]] = {
    "clock": (paint_clock.inputs, paint_clock.paint_clock),
    "day": (paint_day.inputs, paint_day.paint_day),
    "agenda": (paint_agenda.inputs, paint_agenda.paint_agenda),
    "headlines": (paint_headlines.inputs, paint_headlines.paint_headlines),
    "air": (paint_air.inputs, paint_air.paint_air),
    "apple": (paint_apple.inputs, paint_apple.paint_apple),
    "playing": (paint_playing.inputs, paint_playing.paint_playing),
    "laundry": (paint_laundry.inputs, paint_laundry.paint_laundry),
}


_ready: weakref.WeakSet[Store] = weakref.WeakSet()


def ensure_tables(store: Store) -> None:
    """Made on first use: every answer for a panel may need it."""
    if store in _ready:
        return
    with store.connect() as conn:
        conn.executescript(TABLES)
    _ready.add(store)


def key_of(kind: str, data: dict[str, Any]) -> str:
    raw = json.dumps([kind, VERSION, data], sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def attach(store: Store, screens: list[dict[str, Any]], local: datetime) -> None:
    """Gives each screen with a painter its `background` path (`local`: now, in the
    configured zone)."""
    ensure_tables(store)
    for screen in screens:
        painter = PAINTERS.get(screen.get("kind", ""))
        data = painter[0](screen, local) if painter else None
        if data is None:
            continue
        key = key_of(screen["kind"], data)
        with store.connect() as conn:
            added = conn.execute(
                "INSERT OR IGNORE INTO desk_background (key, kind, inputs, made_at) "
                "VALUES (?, ?, ?, ?)", (key, screen["kind"], json.dumps(data), local.isoformat()),
            ).rowcount
            if added:
                conn.execute(
                    "DELETE FROM desk_background WHERE kind = ? AND key NOT IN (SELECT key FROM "
                    "desk_background WHERE kind = ? ORDER BY made_at DESC LIMIT ?)",
                    (screen["kind"], screen["kind"], KEEP))
        screen["background"] = PATH + key


def picture(store: Store, key: str) -> bytes | None:
    """The background `key` as a JPEG, painted on first use; None for an unknown key."""
    ensure_tables(store)
    with store.connect() as conn:
        row = conn.execute("SELECT kind, inputs, jpeg FROM desk_background WHERE key = ?",
                           (key,)).fetchone()
    if row is None or row["kind"] not in PAINTERS:
        return None
    if row["jpeg"] is not None:
        return row["jpeg"]
    painted = PAINTERS[row["kind"]][1](json.loads(row["inputs"]), store)
    if painted is None:
        return None
    data = paint.jpeg(painted)
    with store.connect() as conn:
        conn.execute("UPDATE desk_background SET jpeg = ? WHERE key = ?", (data, key))
    return data
