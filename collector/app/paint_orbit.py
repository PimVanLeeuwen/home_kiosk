"""C, the orbit clock (plan.md M27): space with its stars, a warm sun in the middle and the
three orbits faint around it, for the hour, the minute and the second; the panel moves
the bodies round them (panels/firmware/main/screen_piece.c, the radii shared)."""

from __future__ import annotations

import random
from datetime import datetime
from typing import Any

from PIL import Image

from . import paint
from .paint import SIZE, SS

CENTRE = (360, 360)
ORBITS = (118, 196, 276)  # the hour's, the minute's and the second's (as the panel)


def inputs(screen: dict[str, Any], local: datetime) -> dict[str, Any] | None:
    return {"orbit": 1} if screen.get("present") else None


def paint_orbit(data: dict[str, Any], store: Any = None) -> Image.Image:
    rng = random.Random(42)
    base = paint.vertical(SIZE, [(0, (6, 7, 16)), (1, (10, 9, 22))])
    layer, draw = paint.shapes()
    for _ in range(160):
        x, y = rng.uniform(0, SIZE), rng.uniform(0, SIZE)
        bright = rng.random() ** 2.5
        paint.disc(draw, x, y, 0.5 + 1.3 * bright, (230, 234, 255, round(50 + 150 * bright)))
    base = paint.lay(base, layer)
    paint.glow(base, *CENTRE, 300, (255, 170, 90), 0.22, power=2.2)
    paint.glow(base, *CENTRE, 90, (255, 220, 170), 0.6)
    layer, draw = paint.shapes()
    for r in ORBITS:
        draw.ellipse(((CENTRE[0] - r) * SS, (CENTRE[1] - r) * SS, (CENTRE[0] + r) * SS,
                      (CENTRE[1] + r) * SS), outline=(200, 190, 255, 46), width=SS)
    paint.disc(draw, *CENTRE, 34, (255, 226, 180, 255))
    return paint.grain(paint.lay(base, layer), 42, 3)
