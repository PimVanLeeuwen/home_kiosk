"""K, the countdown (plan.md M27, made into a tunnel on 2026-10-26): a tunnel of light toward
the day, one glowing ring per day left (at most 60) in the colour of the event's calendar,
receding in perspective to a white-hot core, the day itself; faint streaks run out from it.
The panel sends sparks streaming out of the core while it shows (screen_piece.c, the same
core), and lays the number and the words below."""

from __future__ import annotations

import math
import random
from datetime import datetime
from typing import Any

from PIL import Image, ImageChops, ImageDraw

from . import paint
from .paint import SIZE, SS, Colour, hex_colour, mix

CORE = (360, 200)     # the vanishing point: the day (as the panel's sparks)
NEAREST = 400         # the nearest ring's half width
MOST = 60
WHITE: Colour = (255, 255, 255)


def inputs(screen: dict[str, Any], local: datetime) -> dict[str, Any] | None:
    if not screen.get("present"):
        return None
    return {"days": screen["days"], "colour": screen.get("colour") or "#8f80ff"}


def paint_countdown(data: dict[str, Any], store: Any = None) -> Image.Image:
    colour = hex_colour(data["colour"])
    rng = random.Random(data["days"])
    base = Image.new("RGB", (SIZE, SIZE), (0, 0, 0))
    paint.glow(base, *CORE, 520, colour, 0.22, power=1.8)
    # Faint streaks running out from the core: speed.
    streaks = Image.new("L", (SIZE, SIZE), 0)
    draw = ImageDraw.Draw(streaks)
    for _ in range(70):
        a = rng.uniform(0, 2 * math.pi)
        r1, r2 = rng.uniform(40, 120), rng.uniform(260, 620)
        draw.line((CORE[0] + r1 * math.cos(a), CORE[1] + r1 * math.sin(a) * 0.82,
                   CORE[0] + r2 * math.cos(a), CORE[1] + r2 * math.sin(a) * 0.82),
                  fill=rng.randrange(20, 60), width=1)
    base = paint.tint(base, paint.soften(streaks, 1.2), mix(colour, WHITE, 0.5))
    # The rings, far to near: each a day, closing in towards the core in perspective; the
    # far ones white-hot, the near ones deep in the calendar's colour and wide. Drawn twice:
    # soft for their light, then sharp.
    n = max(1, min(MOST, data["days"]))
    layer, draw = paint.shapes()
    for i in range(n, 0, -1):
        depth = i / n                       # 1 at the day, towards 0 near us
        r = NEAREST / (1 + 11 * depth ** 1.1)
        cx, cy = CORE[0], CORE[1] + (1 - depth) ** 1.6 * 70  # the tunnel bends down to us
        ring = mix(mix(colour, (0, 0, 0), 0.25), mix(colour, WHITE, 0.75), depth ** 0.8)
        alpha = round(90 + 165 * depth ** 0.5) if i > 1 else 255
        width = max(2, round((1.0 + 3.5 * (1 - depth) ** 2) * SS))
        draw.ellipse(((cx - r) * SS, (cy - r * 0.86) * SS, (cx + r) * SS, (cy + r * 0.86) * SS),
                     outline=(*ring, alpha), width=width)
    lit = Image.alpha_composite(Image.new("RGBA", layer.size, (0, 0, 0, 255)), layer)
    lit = lit.convert("RGB").resize((SIZE, SIZE), Image.Resampling.LANCZOS)
    for radius in (12, 4):  # light adds up: screened, never darkened at the edges
        base = ImageChops.screen(base, paint.soften(lit, radius))
    base = ImageChops.screen(base, lit)
    # The day: a white-hot core.
    paint.glow(base, *CORE, 120, mix(colour, WHITE, 0.6), 0.7, power=2.2)
    paint.glow(base, *CORE, 58, WHITE, 0.95, power=1.6)
    # Darker at the foot, where the number and the words sit.
    foot = paint.vertical(SIZE, [(0, (0,) * 3), (0.56, (0,) * 3), (0.7, (150,) * 3),
                                 (1, (225,) * 3)]).convert("L")
    base = paint.tint(base, foot, (0, 0, 0))
    return paint.grain(base, 37, 3)
