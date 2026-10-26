"""Media's background (plan.md M27, the redesigned Media): the first download's poster, its
own colours blurred far over the page and darker towards the rows, so the page takes the
colour of what is coming; without a download (or before its poster is in), House's own
violet light. The poster is the small copy the hub already keeps for the panel."""

from __future__ import annotations

import io
from datetime import datetime
from typing import Any

from PIL import Image, ImageEnhance, ImageOps

from . import desk_media, paint, paint_house
from .paint import SIZE


def _key(screen: dict[str, Any]) -> str | None:
    downloads = screen.get("downloads") or []
    path = downloads[0].get("poster") if downloads else None
    return path.removeprefix("/api/desk/poster/") if path else None


def inputs(screen: dict[str, Any], local: datetime) -> dict[str, Any] | None:
    """The poster and whether the hub has it yet: the wash comes once it is in."""
    if not screen.get("present"):
        return None
    key = _key(screen)
    if key and key in desk_media._posters:
        return {"poster": key}
    return paint_house.inputs_for("media")(screen, local)


def paint_media(data: dict[str, Any], store: Any = None) -> Image.Image:
    if "poster" not in data:  # no download, or its poster not in yet: House's light
        return paint_house.paint_house(data)
    poster = desk_media._posters.get(data["poster"])
    if not poster:  # gone since (the hub restarted): the light, until the next answer
        spot = list(paint_house.SCREENS["media"][1])
        return paint_house.paint_house({"colour": paint_house.VIOLET, "spot": spot})
    with Image.open(io.BytesIO(poster)) as raw:
        small = ImageOps.fit(raw.convert("RGB"), (120, 120), Image.Resampling.LANCZOS)
    wash = paint.soften(small, 10).resize((SIZE, SIZE), Image.Resampling.BICUBIC)
    wash = ImageEnhance.Color(wash).enhance(1.5)
    wash = ImageEnhance.Brightness(wash).enhance(0.55)
    dark = paint.vertical(SIZE, [(0, (60,) * 3), (0.4, (150,) * 3), (1, (225,) * 3)]).convert("L")
    wash = paint.tint(wash, dark, (6, 6, 10))
    return paint.grain(wash, 31, 3)
