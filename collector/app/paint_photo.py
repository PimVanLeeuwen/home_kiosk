"""E, the photo of the day (plan.md M27): the picture edge to edge, darkened a little at the
foot, with a frosted glass label there for the words the panel lays on it. Painted from the
preview the hub keeps in memory (app/sources/photo.py)."""

from __future__ import annotations

import io
from datetime import datetime
from typing import Any

from PIL import Image, ImageDraw, ImageOps

from . import paint
from .paint import SIZE, SS
from .sources import photo

GLASS = (36, 560, SIZE - 36, 690)
RADIUS = 24


def inputs(screen: dict[str, Any], local: datetime) -> dict[str, Any] | None:
    return {"asset": screen["asset"]} if screen.get("present") else None


def paint_photo(data: dict[str, Any], store: Any = None) -> Image.Image | None:
    if photo.KEPT.asset != data["asset"] or photo.KEPT.picture is None:
        return None
    with Image.open(io.BytesIO(photo.KEPT.picture)) as raw:
        picture = ImageOps.fit(ImageOps.exif_transpose(raw).convert("RGB"), (SIZE, SIZE),
                               Image.Resampling.LANCZOS)
    foot = paint.vertical(SIZE, [(0, (0,) * 3), (0.6, (0,) * 3), (1, (120,) * 3)]).convert("L")
    base = paint.tint(picture, foot, (0, 0, 0))
    x1, y1, x2, y2 = GLASS
    frosted = paint.soften(base.crop(GLASS), 18)
    frosted = Image.blend(frosted, Image.new("RGB", frosted.size, (12, 11, 18)), 0.42)
    mask = Image.new("L", ((x2 - x1) * SS, (y2 - y1) * SS), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, (x2 - x1) * SS - 1, (y2 - y1) * SS - 1),
                                           radius=RADIUS * SS, fill=255)
    mask = mask.resize((x2 - x1, y2 - y1), Image.Resampling.LANCZOS)
    base.paste(frosted, (x1, y1), mask)
    layer, draw = paint.shapes()
    draw.rounded_rectangle((x1 * SS, y1 * SS, x2 * SS, y2 * SS), radius=RADIUS * SS,
                           outline=(255, 255, 255, 50), width=SS)
    return paint.grain(paint.lay(base, layer), 47, 2)
