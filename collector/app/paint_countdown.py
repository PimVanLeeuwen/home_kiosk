"""K, the countdown (plan.md M27): a ring of dots round the number, one per day left (at
most 120), in the colour of the event's calendar, the nearest day glowing; a soft light in
the same colour behind. The panel lays the number and the words on top."""

from __future__ import annotations

import math
from datetime import datetime
from typing import Any

from PIL import Image

from . import paint
from .paint import SIZE, hex_colour

CENTRE, RADIUS = (360, 290), 214
MOST = 120


def inputs(screen: dict[str, Any], local: datetime) -> dict[str, Any] | None:
    if not screen.get("present"):
        return None
    return {"days": screen["days"], "colour": screen.get("colour") or "#8f80ff"}


def paint_countdown(data: dict[str, Any], store: Any = None) -> Image.Image:
    colour = hex_colour(data["colour"])
    base = Image.new("RGB", (SIZE, SIZE), (0, 0, 0))
    paint.glow(base, *CENTRE, 340, colour, 0.2, power=2.0)
    n = max(1, min(MOST, data["days"]))
    layer, draw = paint.shapes()
    nearest = None
    for i in range(n):
        a = -math.pi / 2 + 2 * math.pi * i / n
        x, y = CENTRE[0] + RADIUS * math.cos(a), CENTRE[1] + RADIUS * math.sin(a)
        if i == 0:
            nearest = (x, y)
        r = 7 if i == 0 else 4.5 if n <= 40 else 3.4
        paint.disc(draw, x, y, r, (*colour, 255 if i == 0 else 190))
    base = paint.lay(base, layer)
    if nearest:
        paint.glow(base, *nearest, 40, colour, 0.7)
    return paint.grain(base, 37, 3)
