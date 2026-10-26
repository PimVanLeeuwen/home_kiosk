"""Code's background (plan.md M27, the redesigned Code): sixteen weeks of contributions as a
small city seen from above at an angle, a block per day, as tall as GitHub's level for it,
in the panels' violets, the weeks running back to front; today's block lit white. The panel
keeps the three lines below and breathes a glow on today's block (`today_point`)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from PIL import Image

from . import paint
from .paint import SIZE, SS

CW, CH = 22, 12.2   # half a block's top: across and down
STEP_UP = 25        # height per level
ORIGIN = (262, 250)  # where the first week's Monday stands: the city centred
# Per level: (right face, left face, top) in GitHub's quartiles in violet, as the old grid.
FACES = [((22, 21, 30), (17, 16, 24), (32, 30, 44)), ((43, 37, 85), (34, 30, 68), (58, 50, 112)),
         ((74, 65, 145), (58, 51, 116), (100, 88, 196)), ((128, 116, 213), (100, 90, 176),
                                                          (162, 148, 255)),
         ((195, 185, 255), (157, 144, 239), (226, 220, 255))]


def _foot(week: int, day: int) -> tuple[float, float]:
    """The centre of a day's tile on the ground."""
    return ORIGIN[0] + (week - day) * CW, ORIGIN[1] + (week + day) * CH


def _height(level: int) -> float:
    return 8 + level * STEP_UP


def today_point(levels: list[int]) -> tuple[int, int]:
    """The top of today's block (the last day), where the panel breathes its glow."""
    if not levels:
        return ORIGIN
    i = len(levels) - 1
    x, y = _foot(i // 7, i % 7)
    return round(x), round(y - _height(min(4, levels[i])))


def inputs(screen: dict[str, Any], local: datetime) -> dict[str, Any] | None:
    if not screen.get("present") or not screen.get("levels"):
        return None
    return {"levels": screen["levels"]}


def _block(draw: Any, x: float, y: float, h: float, faces: tuple, top: tuple) -> None:
    s = SS
    right, left, _ = faces
    draw.polygon([((x + CW) * s, y * s), (x * s, (y + CH) * s), (x * s, (y + CH - h) * s),
                  ((x + CW) * s, (y - h) * s)], fill=(*right, 255))
    draw.polygon([((x - CW) * s, y * s), (x * s, (y + CH) * s), (x * s, (y + CH - h) * s),
                  ((x - CW) * s, (y - h) * s)], fill=(*left, 255))
    draw.polygon([(x * s, (y - h - CH) * s), ((x + CW) * s, (y - h) * s), (x * s, (y - h + CH) * s),
                  ((x - CW) * s, (y - h) * s)], fill=(*top, 255))


def paint_code(data: dict[str, Any], store: Any = None) -> Image.Image:
    levels = data["levels"]
    base = Image.new("RGB", (SIZE, SIZE), (0, 0, 0))
    paint.glow(base, SIZE - 60, -40, 420, (124, 108, 242), 0.2, power=2.4)
    paint.glow(base, 360, 400, 360, (143, 128, 255), 0.16, power=2.0)
    layer, draw = paint.shapes()
    weeks = (len(levels) + 6) // 7
    for s in range(weeks + 7):  # back to front: the sum of week and day
        for week in range(weeks):
            day = s - week
            i = week * 7 + day
            if not 0 <= day < 7 or i >= len(levels):
                continue
            level = min(4, max(0, levels[i]))
            x, y = _foot(week, day)
            faces = FACES[level]
            top = (255, 255, 255) if i == len(levels) - 1 else faces[2]
            _block(draw, x, y, _height(level), faces, top)
    base = paint.lay(base, layer)
    tx, ty = today_point(levels)
    paint.glow(base, tx, ty, 60, (210, 200, 255), 0.5)
    return paint.grain(base, 29, 3)
