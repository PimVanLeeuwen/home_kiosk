"""B, the night sky (plan.md M27): the dark from the zenith down, a faint Milky Way with
its crowd of small stars, the other stars, the constellation that is up drawn in fine
lines, the moon in its phase on its arc, and the town along the bottom with its warm
glow over the roofs; grain. The panel lays the words and the time on top.
"""

from __future__ import annotations

import random
from datetime import datetime
from typing import Any

from PIL import Image, ImageChops

from . import paint, paint_clock
from .paint import SIZE, hex_colour

# The constellations, as points in a 300 x 220 box, and the lines between them.
SHAPES: dict[str, tuple[list[tuple[int, int]], list[tuple[int, int]]]] = {
    "Cassiopeia": ([(0, 60), (70, 130), (140, 70), (210, 150), (290, 40)],
                   [(0, 1), (1, 2), (2, 3), (3, 4)]),
    "the Big Dipper": ([(0, 40), (70, 30), (130, 50), (185, 85), (200, 165), (290, 175),
                        (295, 100)], [(0, 1), (1, 2), (2, 3), (3, 4), (4, 5), (5, 6), (6, 3)]),
    "Orion": ([(60, 0), (200, 20), (110, 95), (130, 105), (150, 115), (40, 210), (230, 200)],
              [(0, 2), (1, 4), (2, 3), (3, 4), (2, 5), (4, 6)]),
}
TOWN = 650  # where the roofs start


def inputs(screen: dict[str, Any], local: datetime) -> dict[str, Any] | None:
    sky = screen.get("horizon")
    if not screen.get("present") or not sky:
        return None
    return {"top": sky["top"], "mid": sky["mid"], "low": sky["low"],
            "at": round(sky["at"] / 10) * 10, "moon": round(sky["moon"] / 20) * 20,
            "shape": screen.get("constellation") or "Cassiopeia", "day": local.date().toordinal()}


def _milky_way(base: Image.Image, rng: random.Random) -> Image.Image:
    band = Image.new("L", (SIZE, SIZE), 0)
    for y in range(SIZE):
        for x in range(0, SIZE, 4):
            d = abs((x - 80) * 0.55 - (y - 60)) / 120  # a diagonal band, top left down
            if d < 1:
                band.putpixel((x, y), round(255 * (1 - d) ** 2))
    band = band.resize((SIZE, SIZE))
    texture = paint.fbm(SIZE, SIZE, rng.randrange(9999), 90)
    band = ImageChops.multiply(paint.soften(band, 6), texture)
    base = paint.tint(base, paint.soften(band, 10), (150, 160, 220), 0.35)
    layer, draw = paint.shapes()
    for _ in range(900):
        x, y = rng.uniform(0, SIZE), rng.uniform(0, TOWN)
        if band.getpixel((round(x) % SIZE, round(y) % SIZE)) > 40:
            paint.disc(draw, x, y, rng.uniform(0.4, 0.9), (230, 234, 255, rng.randrange(60, 170)))
    return paint.lay(base, layer)


def _stars(base: Image.Image, rng: random.Random) -> Image.Image:
    layer, draw = paint.shapes()
    for _ in range(220):
        x, y = rng.uniform(0, SIZE), TOWN * rng.random() ** 1.3
        bright = rng.random() ** 2.6
        paint.disc(draw, x, y, 0.6 + 1.5 * bright, (235, 238, 255, round(80 + 170 * bright)))
    return paint.lay(base, layer)


def _constellation(base: Image.Image, shape: str) -> Image.Image:
    points, lines = SHAPES.get(shape, SHAPES["Cassiopeia"])
    ox, oy = 360, 110
    layer, draw = paint.shapes()
    for a, b in lines:
        (x1, y1), (x2, y2) = points[a], points[b]
        draw.line(((ox + x1) * 2, (oy + y1) * 2, (ox + x2) * 2, (oy + y2) * 2),
                  fill=(190, 200, 255, 70), width=2)
    for x, y in points:
        paint.glow(base, ox + x, oy + y, 10, (170, 185, 255), 0.35)
        paint.disc(draw, ox + x, oy + y, 2.4, (245, 247, 255, 255))
    return paint.lay(base, layer)


def _town(base: Image.Image, rng: random.Random) -> Image.Image:
    paint.glow(base, SIZE / 2, SIZE + 40, 520, (255, 160, 90), 0.22, power=1.8)
    layer, draw = paint.shapes()
    x = 0.0
    while x < SIZE:
        w, h = rng.uniform(26, 70), rng.uniform(24, 70)
        top = TOWN + 70 - h
        draw.rectangle((x * 2, top * 2, (x + w) * 2, SIZE * 2), fill=(4, 4, 8, 255))
        if rng.random() < 0.5:  # a pitched roof
            draw.polygon([(x * 2, top * 2), ((x + w / 2) * 2, (top - w * 0.35) * 2),
                          ((x + w) * 2, top * 2)], fill=(4, 4, 8, 255))
        for _ in range(rng.randrange(0, 3)):  # a lit window
            wx, wy = x + rng.uniform(6, w - 10), top + rng.uniform(8, h - 8)
            draw.rectangle((wx * 2, wy * 2, (wx + 5) * 2, (wy + 6) * 2), fill=(255, 196, 120, 200))
        x += w + rng.uniform(-4, 6)
    return paint.lay(base, layer)


def paint_night(data: dict[str, Any], store: Any = None) -> Image.Image:
    top, mid, low = (hex_colour(data[k]) for k in ("top", "mid", "low"))
    rng = random.Random(data["day"])
    base = paint.vertical(SIZE, [(0, top), (0.6, mid), (1, low)])
    base = _milky_way(base, rng)
    base = _stars(base, rng)
    base = _constellation(base, data["shape"])
    paint_clock._body(base, {"body": "moon", "at": data["at"], "moon": data["moon"],
                             "veiled": False}, top, mid, low)
    base = _town(base, rng)
    return paint.grain(base, data["day"], 3)
