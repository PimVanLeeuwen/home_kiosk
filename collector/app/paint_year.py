"""H, the year (plan.md M27): the year as a dial of 53 week-spokes from the top, clockwise,
each spoke its seven days from Monday inside to Sunday outside; the days gone in violet,
today glowing white, the days to come faint; the months' first days a touch brighter. The
panel lays the day's number in the middle and the words around it."""

from __future__ import annotations

import math
from datetime import date, datetime
from typing import Any

from PIL import Image

from . import paint
from .paint import SIZE

CENTRE = (360, 350)
INNER, STEP = 132, 17  # the first day's radius, and the step outwards per weekday
VIOLET = (143, 128, 255)


def inputs(screen: dict[str, Any], local: datetime) -> dict[str, Any] | None:
    if not screen.get("present"):
        return None
    return {"year": screen["year"], "today": screen["today"], "days": screen["days"]}


def paint_year(data: dict[str, Any], store: Any = None) -> Image.Image:
    base = Image.new("RGB", (SIZE, SIZE), (0, 0, 0))
    paint.glow(base, *CENTRE, 330, VIOLET, 0.16, power=2.0)
    first = date(data["year"], 1, 1)
    offset = first.weekday()  # 1 January's weekday: where the first spoke starts
    layer, draw = paint.shapes()
    today_at = None
    for n in range(1, data["days"] + 1):
        slot = n - 1 + offset
        week, weekday = divmod(slot, 7)
        angle = -math.pi / 2 + 2 * math.pi * week / 53
        r = INNER + weekday * STEP
        x, y = CENTRE[0] + r * math.cos(angle), CENTRE[1] + r * math.sin(angle)
        month_start = date.fromordinal(first.toordinal() + n - 1).day == 1
        if n < data["today"]:
            colour = (*VIOLET, 230 if month_start else 170)
        elif n == data["today"]:
            colour, today_at = (255, 255, 255, 255), (x, y)
        else:
            colour = (255, 255, 255, 70 if month_start else 34)
        paint.disc(draw, x, y, 4.6 if n == data["today"] else 3.4, colour)
    base = paint.lay(base, layer)
    if today_at:
        paint.glow(base, *today_at, 34, (255, 255, 255), 0.7)
    return paint.grain(base, data["year"], 3)
