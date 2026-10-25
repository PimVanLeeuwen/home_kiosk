"""The Apple devices screen's background (plan.md M27, the lifted Apple devices): the
rooms where something plays lit from within in the colour of what plays (blue for video,
violet for music), spilling softly past their walls; the violet corner and grain. The
panel draws the rooms as glass on top, with the devices and the mesh between them.

The room layout is the panel's (panels/firmware/main/screen_apple.c, place()).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from PIL import Image

from . import paint
from .paint import SIZE, hex_colour

LEFT, WIDTH, TOP, PLAN_H, GAP = 36, 648, 90, 420, 12
VIOLET = (124, 108, 242)


def centre(i: int, count: int) -> tuple[float, float]:
    half = (WIDTH - GAP) / 2
    if count == 1:
        return LEFT + WIDTH / 2, TOP + PLAN_H / 2
    if i == 0:
        return LEFT + half / 2, TOP + PLAN_H / 2
    height = PLAN_H if count == 2 else (PLAN_H - GAP) / 2
    return LEFT + half + GAP + half / 2, TOP + (i - 1) * (height + GAP) + height / 2


def inputs(screen: dict[str, Any], local: datetime) -> dict[str, Any] | None:
    """Which rooms play, and in what colour: changes when something starts or stops."""
    rooms = screen.get("rooms") or []
    if not screen.get("present") or not rooms:
        return None
    return {"count": len(rooms), "glows": [r.get("glow") for r in rooms]}


def paint_apple(data: dict[str, Any], store: Any = None) -> Image.Image:
    base = Image.new("RGB", (SIZE, SIZE), (0, 0, 0))
    paint.glow(base, SIZE - 60, -40, 420, VIOLET, 0.18, power=2.4)
    for i, glow in enumerate(data["glows"]):
        if glow:
            x, y = centre(i, data["count"])
            paint.glow(base, x, y, 300, hex_colour(glow), 0.3, power=2.0)
    return paint.grain(base, 13, 3)
