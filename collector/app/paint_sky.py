"""A, the living sky (plan.md M27): the whole screen in the colours of the sky now, from
the zenith down, with wide ribbons of light flowing slowly across it (they move a little
every few minutes), the sun's glow low on its arc, greyer under an overcast sky; grain.
The panel lays the time and the words on top (app/desk_pieces.py, sky_screen).
"""

from __future__ import annotations

import math
import random
from datetime import datetime
from typing import Any

from PIL import Image, ImageChops, ImageDraw

from . import paint
from .paint import SIZE, Colour, hex_colour, mix

WHITE: Colour = (255, 255, 255)


def inputs(screen: dict[str, Any], local: datetime) -> dict[str, Any] | None:
    sky = screen.get("horizon")
    if not screen.get("present") or not sky:
        return None
    minute = local.hour * 60 + local.minute
    return {"top": sky["top"], "mid": sky["mid"], "low": sky["low"], "body": sky["body"],
            "at": round(sky["at"] / 10) * 10, "veiled": sky["veiled"],
            "day": local.date().toordinal(), "drift": minute // 3}


def _wave(base: Image.Image, crest: float, amplitude: float, period: float, phase: float,
          colour: Colour, rim: Colour) -> Image.Image:
    """One layer of light: a smooth wave from its crest down to the foot of the screen, with a
    fine light edge along the crest (crisp, as the clouds: the owner's wish, 2026-10-25)."""
    line = [(x, crest + amplitude * math.sin(x / period + phase)
             + amplitude * 0.35 * math.sin(x / (period * 0.43) - phase * 1.7))
            for x in range(-8, SIZE + 16, 6)]
    mask = Image.new("L", (SIZE * 2, SIZE * 2), 0)
    ImageDraw.Draw(mask).polygon([(x * 2, y * 2) for x, y in line] + [(SIZE * 2, SIZE * 2),
                                                                      (0, SIZE * 2)], fill=255)
    mask = mask.resize((SIZE, SIZE), Image.Resampling.LANCZOS)
    out = paint.tint(base, mask, colour)
    edge = ImageChops.subtract(mask, ImageChops.offset(mask, 0, 3))
    return paint.tint(out, paint.soften(edge, 1), rim, 0.7)


def paint_sky(data: dict[str, Any], store: Any = None) -> Image.Image:
    top, mid, low = (hex_colour(data[k]) for k in ("top", "mid", "low"))
    base = paint.vertical(SIZE, [(0, top), (0.55, mid), (1, low)])
    rng = random.Random(data["day"])
    shift = data["drift"] * 0.02
    # The sun first, riding low just over the waves (the time is above it), sinking behind
    # them at either end.
    if data["body"] == "sun":
        t = data["at"] / 1000
        x, y = 60 + 600 * t, 440 - 90 * math.sin(math.pi * t)  # low over the waves
        strength = 0.22 if data["veiled"] else 0.42
        paint.glow(base, x, y, 380, (255, 205, 150), strength, power=2.4)
        paint.glow(base, x, y, 80, (255, 236, 210), strength * 1.3)
        layer, draw = paint.shapes()
        paint.disc(draw, x, y, 30, (255, 238, 214, 140 if data["veiled"] else 255))
        base = paint.lay(base, layer)
    # Four waves of light, lighter and warmer behind, darker in front where the words sit.
    for i in range(4):
        depth = i / 3
        colour = mix(mix(low, WHITE, 0.22 - 0.12 * depth), mix(top, (0, 0, 0), 0.3), depth * 0.85)
        rim = mix(colour, WHITE, 0.35 - 0.15 * depth)
        base = _wave(base, 400 + i * 70 + rng.uniform(-12, 12), rng.uniform(14, 26),
                     rng.uniform(90, 150), shift * (0.6 + 0.5 * i) + rng.uniform(0, 6), colour, rim)
    return paint.grain(base, data["day"], 3)
