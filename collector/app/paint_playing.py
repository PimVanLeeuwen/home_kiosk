"""Now Playing's background (plan.md M27, the lifted Now Playing): the cover's own
colours wash the whole screen, blurred far and saturated, darker towards the words and
the controls, with a little more light behind the cover; grain. The panel draws the
cover, the record behind it, the words and the controls on top.
"""

from __future__ import annotations

import io
from datetime import datetime
from typing import Any

from PIL import Image, ImageEnhance, ImageOps

from . import paint
from .paint import SIZE
from .store import Store

COVER_CENTRE = (36 + 144, 36 + 144)  # panels/firmware/main/screen_playing.c


def inputs(screen: dict[str, Any], local: datetime) -> dict[str, Any] | None:
    """The cover (its key): the wash changes only with the cover."""
    cover = screen.get("cover")
    if not screen.get("present") or not cover:
        return None
    return {"cover": cover.split("/")[4]}  # /api/desk/cover/<key>/big


def _cover(store: Store, key: str) -> bytes | None:
    """The cover as the hub keeps it (app/sources/spotify.py), once it has fetched it."""
    with store.connect() as conn:
        row = conn.execute("SELECT image FROM music_cover WHERE key = ?", (key,)).fetchone()
    return row["image"] if row else None


def paint_playing(data: dict[str, Any], store: Store) -> Image.Image | None:
    stored = _cover(store, data["cover"])
    if not stored:
        return None
    with Image.open(io.BytesIO(stored)) as raw:
        cover = ImageOps.fit(raw.convert("RGB"), (SIZE, SIZE), Image.Resampling.LANCZOS)
    wash = paint.soften(cover.resize((180, 180), Image.Resampling.BILINEAR), 18)
    wash = wash.resize((SIZE, SIZE), Image.Resampling.BICUBIC)
    wash = ImageEnhance.Color(wash).enhance(1.6)
    wash = ImageEnhance.Brightness(wash).enhance(0.62)
    # Darker towards the words and the controls, so they read in white.
    dark = paint.vertical(SIZE, [(0, (40,) * 3), (0.45, (110,) * 3), (1, (215,) * 3)]).convert("L")
    wash = paint.tint(wash, dark, (6, 6, 10))
    paint.glow(wash, *COVER_CENTRE, 300, (255, 255, 255), 0.08, power=2.4)
    return paint.grain(wash, 17, 3)
