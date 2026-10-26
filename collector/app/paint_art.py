"""F, the art of the day (plan.md M27): a flow field, a few thousand fine strokes following
a smooth field of directions, in a palette of the season, new each day (seeded by the date)
and numbered by the panel's words. Painted once a day."""

from __future__ import annotations

import math
import random
from datetime import datetime
from typing import Any

from PIL import Image

from . import paint
from .paint import SIZE, SS, hex_colour

PALETTES = {
    "autumn": ["#f2a65a", "#e5646a", "#c46a2c", "#8f80ff", "#ffd9a8"],
    "winter": ["#6aa8f0", "#c4dcff", "#8f80ff", "#e8ecff", "#3b5bd9"],
    "spring": ["#3fb97f", "#9ff0c6", "#f08aa8", "#ffe1d6", "#8f80ff"],
    "summer": ["#f6c56b", "#3fd0c0", "#ff9a6a", "#fff3c4", "#6aa8f0"],
}


def inputs(screen: dict[str, Any], local: datetime) -> dict[str, Any] | None:
    if not screen.get("present"):
        return None
    return {"day": screen["day"], "season": screen["season"]}


def paint_art(data: dict[str, Any], store: Any = None) -> Image.Image:
    rng = random.Random(data["day"])
    palette = [hex_colour(c) for c in PALETTES.get(data["season"], PALETTES["autumn"])]
    field = paint.fbm(SIZE, SIZE, rng.randrange(1 << 30), 220, octaves=3)
    turn = rng.uniform(1.5, 3.5)  # how strongly the field turns the strokes
    base = Image.new("RGB", (SIZE, SIZE), (6, 6, 10))
    paint.glow(base, rng.uniform(200, 520), rng.uniform(200, 520), 420, palette[0], 0.12)
    layer, draw = paint.shapes()
    for _ in range(2600):
        x, y = rng.uniform(0, SIZE), rng.uniform(0, SIZE)
        colour = palette[min(len(palette) - 1, int(rng.random() ** 1.6 * len(palette)))]
        alpha = rng.randrange(60, 200)
        width = rng.choice((1, 1, 2, 3)) * SS
        points = [(x * SS, y * SS)]
        for _ in range(rng.randrange(14, 46)):
            angle = field.getpixel((int(x) % SIZE, int(y) % SIZE)) / 255 * math.pi * turn
            x, y = x + 4 * math.cos(angle), y + 4 * math.sin(angle)
            if not (0 <= x < SIZE and 0 <= y < SIZE):
                break
            points.append((x * SS, y * SS))
        if len(points) > 3:
            draw.line(points, fill=(*colour, alpha), width=width, joint="curve")
    base = paint.lay(base, layer)
    # Full bleed, quieter at the top and the foot where the words sit.
    quiet = paint.vertical(SIZE, [(0, (200,) * 3), (0.14, (0,) * 3), (0.84, (0,) * 3),
                                  (1, (210,) * 3)]).convert("L")
    base = paint.tint(base, quiet, (6, 6, 10))
    return paint.grain(base, data["day"], 3)
