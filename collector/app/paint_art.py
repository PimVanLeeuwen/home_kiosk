"""F, the art of the day (plan.md M27, a landscape since 2026-10-26): ridges fading into mist
under the sky, a low sun or moon with its glow, in a palette of the season; new each day
(seeded by the date): the ridges, the light (dawn, dusk or night, with stars), where the sun
or moon stands. The panel's words name it ("Ridges at dusk, autumn") and number it. Painted
once a day."""

from __future__ import annotations

import math
import random
from datetime import datetime
from typing import Any

from PIL import Image, ImageDraw

from . import paint
from .paint import SIZE, SS, Colour, hex_colour, mix

PALETTES = {
    "autumn": ["#f2a65a", "#e5646a", "#c46a2c", "#8f80ff", "#ffd9a8"],
    "winter": ["#6aa8f0", "#c4dcff", "#8f80ff", "#e8ecff", "#3b5bd9"],
    "spring": ["#3fb97f", "#9ff0c6", "#f08aa8", "#ffe1d6", "#8f80ff"],
    "summer": ["#f6c56b", "#3fd0c0", "#ff9a6a", "#fff3c4", "#6aa8f0"],
}
RIDGES = 6
NEAR: Colour = (6, 6, 12)


def light(day: int) -> str:
    """The day's light: "dawn", "dusk" or "night" (the same for the painter and the words)."""
    pick = random.Random(day * 7919).random()
    return "night" if pick < 0.35 else "dusk" if pick < 0.75 else "dawn"


def inputs(screen: dict[str, Any], local: datetime) -> dict[str, Any] | None:
    if not screen.get("present"):
        return None
    return {"day": screen["day"], "season": screen["season"]}


def paint_art(data: dict[str, Any], store: Any = None) -> Image.Image:
    rng = random.Random(data["day"])
    palette = [hex_colour(c) for c in PALETTES.get(data["season"], PALETTES["autumn"])]
    when = light(data["day"])
    if when == "night":
        top, low = (8, 8, 20), (30, 26, 60)
    elif when == "dusk":
        top, low = mix((14, 12, 30), palette[3], 0.12), mix(palette[0], (255, 220, 190), 0.3)
    else:  # dawn: cooler, the season's palest colour
        top, low = mix((10, 10, 26), palette[3], 0.15), mix(palette[4], (210, 220, 255), 0.35)
    base = paint.vertical(SIZE, [(0, top), (0.62, low), (1, low)])
    # The ridges, far to near: a horizon, a height and a few waves each.
    ridges = []
    for i in range(RIDGES):
        t = i / (RIDGES - 1)
        waves = [(weight, rng.uniform(0.6, 1.4) * freq, rng.uniform(0, 2 * math.pi))
                 for weight, freq in ((1, 1.3), (0.45, 2.9), (0.18, 6.7), (0.06, 15))]
        ridges.append((330 + t * 300, (40 + 70 * (1 - t)) * rng.uniform(0.6, 1.2), waves))

    def crest(ridge: tuple[float, float, list], x: float) -> float:
        horizon, height, waves = ridge
        return horizon - height * sum(w * math.sin(x / SIZE * math.pi * f + p) for w, f, p in waves)

    # The sun or the moon above the skyline, now and then low enough to touch it.
    sx = rng.uniform(170, 550)
    sy = min(min(crest(r, sx) for r in ridges) - rng.uniform(10, 120), 330)
    if when == "night":
        layer, draw = paint.shapes()
        for _ in range(160):
            paint.disc(draw, rng.random() * SIZE, rng.random() * 420,
                       rng.choice((0.6, 0.9, 1.2)), (255, 255, 255, rng.randint(50, 170)))
        base = paint.lay(base, layer)
    glow = (180, 190, 255) if when == "night" else (255, 210, 160)
    paint.glow(base, sx, sy, 260, glow, 0.35, power=1.8)
    layer, draw = paint.shapes()
    paint.disc(draw, sx, sy, 24 if when == "night" else 34,
               (236, 238, 255, 255) if when == "night" else (255, 244, 222, 255))
    base = paint.lay(base, layer)
    # Each ridge over the last, mist rising in front of each.
    far = mix(low, top, 0.25)
    for i, ridge in enumerate(ridges):
        t = i / (RIDGES - 1)
        horizon = ridge[0]
        points = [(x * SS, crest(ridge, x) * SS) for x in range(0, SIZE + 4, 4)]
        mask = Image.new("L", (SIZE * SS, SIZE * SS), 0)
        ImageDraw.Draw(mask).polygon(points + [(SIZE * SS, SIZE * SS), (0, SIZE * SS)], fill=255)
        mask = mask.resize((SIZE, SIZE), Image.Resampling.LANCZOS)
        colour = mix(mix(far, NEAR, t ** 0.8), palette[4 if when == "night" else 1],
                     0.12 * (1 - t))
        base = paint.tint(base, mask, colour)
        if i < RIDGES - 1:
            mist = paint.vertical(SIZE, [(0, (0,) * 3), (max(0, (horizon - 20) / SIZE), (0,) * 3),
                                         (min(1, (horizon + 90) / SIZE), (110,) * 3),
                                         (1, (0,) * 3)]).convert("L")
            base = paint.tint(base, mist, low, 0.35)
    # Darker behind the words at the top and the foot.
    quiet = paint.vertical(SIZE, [(0, (170,) * 3), (0.14, (0,) * 3), (0.86, (0,) * 3),
                                  (1, (150,) * 3)]).convert("L")
    return paint.grain(paint.tint(base, quiet, (6, 6, 12)), data["day"], 3)
