"""The cover wall's background (plan.md M27, M): the colour of what plays (or played last)
rising from the foot of the screen, dark at the top where the header sits, and a soft light
behind the tile that plays. The panel draws the covers, their names and the words on top
(panels/firmware/main/screen_music.c, whose grid this shares)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from PIL import Image

from . import paint
from .paint import SIZE, hex_colour, mix

# The wall's grid, as screen_music.c lays it out: four covers a row.
LEFT, COVER, GAP = 36, 144, 24
ROW_TOPS = (136, 392)


def tile_centre(row: int, column: int) -> tuple[int, int]:
    return LEFT + column * (COVER + GAP) + COVER // 2, ROW_TOPS[row] + COVER // 2


def inputs(screen: dict[str, Any], local: datetime) -> dict[str, Any] | None:
    if not screen.get("present"):
        return None
    lit = None
    for row, key in enumerate(("favourites", "recent")):
        for column, tile in enumerate(screen.get(key) or []):
            if tile.get("playing"):
                lit = [row, column]
    return {"colour": screen.get("colour") or "#7c6cf2", "lit": lit}


def paint_music(data: dict[str, Any], store: Any = None) -> Image.Image:
    colour = hex_colour(data["colour"])
    deep = mix(colour, (0, 0, 0), 0.55)
    base = paint.vertical(SIZE, [(0, (4, 4, 7)), (0.32, mix(deep, (4, 4, 7), 0.7)),
                                 (0.78, deep), (1, mix(deep, (0, 0, 0), 0.35))])
    paint.glow(base, SIZE // 2, SIZE + 120, 640, colour, 0.32, power=1.6)
    if data.get("lit"):
        x, y = tile_centre(*data["lit"])
        paint.glow(base, x, y, 190, mix(colour, (255, 255, 255), 0.35), 0.3, power=2.0)
    return paint.grain(base, 29, 3)
