"""Recipe photos (plan.md M30), stored small like the headline pictures: a lead at most 900 px
wide for the recipe page and a 240 px square for the list. The original is never kept.
"""

from __future__ import annotations

import io
from datetime import UTC, datetime
from typing import Literal

from PIL import Image, ImageOps

from ..store import Store

LEAD_WIDTH = 900
THUMB_SIZE = 240
WEBP_QUALITY = 80
MAX_BYTES = 20 * 1024 * 1024
MAX_PIXELS = 60_000_000  # a phone photo is about 12 to 48 MP

TABLES = """
CREATE TABLE IF NOT EXISTS recipe_photo (
    recipe_id  TEXT PRIMARY KEY REFERENCES recipe(id) ON DELETE CASCADE,
    lead       BLOB NOT NULL,
    thumb      BLOB NOT NULL,
    updated_at TEXT NOT NULL
);
"""

Size = Literal["lead", "thumb"]


def shrink(data: bytes) -> tuple[bytes, bytes]:
    """(lead, thumbnail) as WebP; raises ValueError for anything that is not a usable picture."""
    if len(data) > MAX_BYTES:
        raise ValueError("photo too large")
    try:
        with Image.open(io.BytesIO(data)) as raw:
            if raw.width * raw.height > MAX_PIXELS:
                raise ValueError("photo too large")
            picture = ImageOps.exif_transpose(raw).convert("RGB")
    except (OSError, Image.DecompressionBombError) as exc:
        raise ValueError("not a picture") from exc
    width = min(picture.width, LEAD_WIDTH)
    height = round(picture.height * width / picture.width)
    lead, thumb = io.BytesIO(), io.BytesIO()
    picture.resize((width, height), Image.Resampling.LANCZOS).save(
        lead, "WEBP", quality=WEBP_QUALITY)
    ImageOps.fit(picture, (THUMB_SIZE, THUMB_SIZE), Image.Resampling.LANCZOS).save(
        thumb, "WEBP", quality=WEBP_QUALITY)
    return lead.getvalue(), thumb.getvalue()


def put(store: Store, recipe_id: str, data: bytes, now: datetime | None = None) -> None:
    lead, thumb = shrink(data)
    stamp = (now or datetime.now(UTC)).isoformat(timespec="seconds")
    with store.connect() as conn:
        conn.execute(
            "INSERT INTO recipe_photo (recipe_id, lead, thumb, updated_at) VALUES (?, ?, ?, ?) "
            "ON CONFLICT(recipe_id) DO UPDATE SET lead = excluded.lead, "
            "thumb = excluded.thumb, updated_at = excluded.updated_at",
            (recipe_id, lead, thumb, stamp))


def get(store: Store, recipe_id: str, size: Size) -> tuple[bytes, str] | None:
    """The photo's bytes and when it was stored (for the address the page asks for)."""
    column = "lead" if size == "lead" else "thumb"
    with store.connect() as conn:
        row = conn.execute(f"SELECT {column} AS data, updated_at FROM recipe_photo "
                           "WHERE recipe_id = ?", (recipe_id,)).fetchone()
    return (row["data"], row["updated_at"]) if row else None


def stamps(store: Store) -> dict[str, str]:
    """When each recipe's photo was stored, by recipe id; a recipe without one is missing."""
    with store.connect() as conn:
        rows = conn.execute("SELECT recipe_id, updated_at FROM recipe_photo").fetchall()
    return {r["recipe_id"]: r["updated_at"] for r in rows}


def delete(store: Store, recipe_id: str) -> None:
    with store.connect() as conn:
        conn.execute("DELETE FROM recipe_photo WHERE recipe_id = ?", (recipe_id,))
