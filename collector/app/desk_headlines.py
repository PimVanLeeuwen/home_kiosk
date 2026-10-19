"""The Now panel's headlines screen (plan.md M20): the three stories of the
hub's headlines (app/news/headlines.py), worded for the panel, and their
pictures as small JPEGs the panel's hardware decoder reads. A tap on a story
saves it to Readeck (`save`, with the board's device key); the hub remembers
which stories were saved, so their bookmarks stay filled.

The pictures come only from the copies the hub already stored as WebP (never
from a news site), cut to the panel's sizes: the lead 640 x 320 under its
story, the others 112 x 112 beside theirs.
"""

from __future__ import annotations

import io
from collections import OrderedDict
from datetime import UTC, datetime
from typing import Any, Literal

from PIL import Image, ImageOps

from .news import headlines
from .panel_text import latin1
from .sources import readeck
from .store import Store

TABLES = """
CREATE TABLE IF NOT EXISTS desk_saved (
    article_id TEXT PRIMARY KEY,
    saved_at   TEXT NOT NULL,
    board      TEXT NOT NULL      -- the MAC of the panel it was saved from
);
"""
KEEP_SAVED_DAYS = 30

LEAD = (640, 320)  # multiples of 16: the decoder works in 16 x 16 blocks
THUMB = (112, 112)
JPEG_QUALITY = 82
_made: OrderedDict[tuple[str, str], bytes] = OrderedDict()  # the last few, as the panels ask often
KEEP = 12


def ensure_tables(store: Store) -> None:
    with store.connect() as conn:
        conn.executescript(TABLES)


def _saved(store: Store) -> set[str]:
    with store.connect() as conn:
        return {r["article_id"] for r in conn.execute("SELECT article_id FROM desk_saved")}


async def save(cfg: dict[str, Any], store: Store, article_id: str, board: str,
               now: datetime | None = None) -> bool:
    """Saves one of the shown headlines to Readeck; False when it is not one of them.
    Saving again changes nothing. Raises readeck.SaveError with a short reason."""
    cached = store.get_cache(headlines.CACHE_KEY) or {}
    item = next((i for i in cached.get("items") or [] if i["id"] == article_id), None)
    if item is None:
        return False
    if article_id in _saved(store):
        return True
    await readeck.save(cfg, item["url"], item["title"])
    now = now or datetime.now(UTC)
    with store.connect() as conn:
        conn.execute("INSERT OR IGNORE INTO desk_saved (article_id, saved_at, board)"
                     " VALUES (?, ?, ?)", (article_id, now.isoformat(), board))
        conn.execute("DELETE FROM desk_saved WHERE saved_at < datetime(?, ?)",
                     (now.isoformat(), f"-{KEEP_SAVED_DAYS} days"))
    return True


def age(published: str, now: datetime) -> str:
    minutes = max(0, int((now - datetime.fromisoformat(published)).total_seconds() // 60))
    if minutes < 60:
        return f"{minutes} min"
    if minutes < 24 * 60:
        return f"{minutes // 60} h"
    return f"{minutes // (24 * 60)} d"


def headlines_screen(store: Store, now: datetime) -> dict[str, Any]:
    cached = store.get_cache(headlines.CACHE_KEY) or {}
    items = (cached.get("items") or [])[:3]
    if not items:
        return {"kind": "headlines", "stale": False, "present": False}
    saved = _saved(store)
    stories = []
    for i, item in enumerate(items):
        size = "lead" if i == 0 else "thumb"
        has = item.get("image") == "lead" or (size == "thumb" and item.get("image") == "thumb")
        stories.append({
            "id": item["id"], "title": latin1(item["title"]), "source": latin1(item["source"]),
            "age": age(item["published"], now),
            "picture": f"/api/desk/picture/{item['id']}/{size}" if has else None,
            "saved": item["id"] in saved,
        })
    return {"kind": "headlines", "stale": bool(cached.get("stale")), "present": True,
            "stories": stories}


def picture(store: Store, article_id: str, size: Literal["lead", "thumb"]) -> bytes | None:
    """A stored picture as a baseline JPEG at the panel's size, or None."""
    key = (article_id, size)
    if key in _made:
        _made.move_to_end(key)
        return _made[key]
    stored = headlines.picture(store, article_id, size)
    if not stored:
        return None
    with Image.open(io.BytesIO(stored)) as image:
        fitted = ImageOps.fit(image.convert("RGB"), LEAD if size == "lead" else THUMB,
                              Image.Resampling.LANCZOS)
    out = io.BytesIO()
    # Baseline with 4:2:0 subsampling: what the ESP32-P4's JPEG decoder takes.
    fitted.save(out, "JPEG", quality=JPEG_QUALITY, progressive=False, subsampling="4:2:0")
    _made[key] = out.getvalue()
    while len(_made) > KEEP:
        _made.popitem(last=False)
    return _made[key]
