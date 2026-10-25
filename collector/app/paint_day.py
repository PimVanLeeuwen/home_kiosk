"""The Day screen's background (plan.md M27, the lifted Day): the night hours as deep
fields with stars in them, the day's warmth as a soft light around its warmest hour,
a little violet in the corner as on every panel screen, and grain. The panel draws the
chart on top (the fill, the glowing line, the bars, the breathing dot at now).

The geometry is the panel's (panels/firmware/main/screen_day.c): hours 6 to 24 across
from x 36, 648 wide; the night fields from 256 to 558, soft at every edge.
"""

from __future__ import annotations

import random
from datetime import datetime
from typing import Any

from PIL import Image, ImageChops

from . import paint
from .paint import SIZE, Colour

LEFT, WIDTH = 36, 648
FIELD_TOP, FIELD_BOTTOM = 256, 558  # CHART_TOP + 20 to FILL_BOTTOM + 30
NIGHT: Colour = (11, 12, 32)
WARM: Colour = (255, 184, 107)
VIOLET: Colour = (124, 108, 242)


def inputs(screen: dict[str, Any], local: datetime) -> dict[str, Any] | None:
    """What the picture shows: the sun's times, the warmest hour and the date (for the
    stars). It changes once a day or with the forecast, not with the clock."""
    if not screen.get("present") or screen.get("sunrise_minute") is None:
        return None
    temperatures = screen.get("temperatures") or []
    peak = max(range(len(temperatures)), key=temperatures.__getitem__) if temperatures else 8
    return {"sunrise": screen["sunrise_minute"], "sunset": screen["sunset_minute"],
            "peak": peak, "day": local.date().toordinal()}


def x_of(hour: float) -> float:
    return LEFT + (hour - 6) / 18 * WIDTH


def _dark(hour: float, sunrise: float, sunset: float) -> float:
    """As the panel: 1 at night, 0 by day, an hour soft around sunrise and sunset."""
    return max(0.0, min(1.0, max(min((sunrise - hour) + 0.5, 1), min((hour - sunset) + 0.5, 1))))


def paint_day(data: dict[str, Any], store: Any = None) -> Image.Image:
    sunrise, sunset = data["sunrise"] / 60, data["sunset"] / 60
    base = Image.new("RGB", (SIZE, SIZE), (0, 0, 0))
    paint.glow(base, SIZE - 60, -40, 420, VIOLET, 0.22, power=2.4)

    # The day's warmth: a soft light around its warmest hour, low over the chart.
    paint.glow(base, x_of(6 + data["peak"]), 430, 330, WARM, 0.12, power=2.2)

    # The night fields: a row of how dark each column is, times a column fading in and out.
    row = Image.new("L", (SIZE, 1), 0)
    for x in range(LEFT, LEFT + WIDTH):
        row.putpixel((x, 0), round(255 * _dark(6 + (x - LEFT) / WIDTH * 18, sunrise, sunset)))
    column = Image.new("L", (1, SIZE), 0)
    for y in range(FIELD_TOP, FIELD_BOTTOM):
        edge = min((y - FIELD_TOP) / 90, (FIELD_BOTTOM - y) / 90, 1)
        column.putpixel((0, y), round(255 * edge))
    # Soft at the chart's own ends too, and blurred so no edge reads as a box.
    for x in range(SIZE):
        end = min((x - LEFT + 30) / 60, (LEFT + WIDTH + 30 - x) / 60, 1)
        row.putpixel((x, 0), round(row.getpixel((x, 0)) * max(0.0, end)))
    mask = ImageChops.multiply(row.resize((SIZE, SIZE)), column.resize((SIZE, SIZE)))
    mask = paint.soften(mask, 16)
    field = paint.vertical(SIZE, [(0, NIGHT), (0.45, (15, 16, 46)), (0.8, (11, 12, 34)),
                                  (1, NIGHT)])
    base = paint.tint(base, mask, field)

    # Stars, only well inside the night: the same ones all day, new ones each day.
    rng = random.Random(data["day"])
    layer, draw = paint.shapes()
    for _ in range(140):
        x, y = rng.uniform(LEFT, LEFT + WIDTH), rng.uniform(FIELD_TOP + 30, FIELD_BOTTOM - 30)
        strength = mask.getpixel((round(x), round(y))) / 255
        if strength < 0.7:
            continue
        bright = rng.random() ** 2.2
        alpha = round((60 + 170 * bright) * strength)
        paint.disc(draw, x, y, 0.6 + 1.2 * bright, (232, 236, 255, alpha))
    base = paint.lay(base, layer)
    return paint.grain(base, data["day"], 3)
