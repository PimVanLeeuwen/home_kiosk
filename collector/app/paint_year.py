"""H, the year (plan.md M27, made an orbit on 2026-10-26): the year as Earth's path round a
warm sun, seen at a slant, under the stars; a tick on the path where each month starts, the
days gone as a glowing trail in the colours of the seasons (winter blue, spring green, summer
gold, autumn amber, the winter violet again), brightest near today; Earth at today, lit on its
sun side. The panel lays the day's number and the words, and breathes a halo round Earth
(screen_piece.c, at `earth`)."""

from __future__ import annotations

import math
import random
from datetime import date, datetime
from typing import Any

from PIL import Image, ImageChops, ImageDraw, ImageFilter

from . import paint
from .paint import SIZE, Colour, mix

SUN = (360, 380)
RX, RY = 292, 118  # the orbit, flattened by the slant
SEASONS: tuple[tuple[float, Colour], ...] = (
    (0, (110, 150, 255)), (0.22, (120, 220, 170)), (0.45, (255, 214, 120)),
    (0.7, (255, 150, 80)), (0.92, (140, 120, 255)), (1, (110, 150, 255)))


def inputs(screen: dict[str, Any], local: datetime) -> dict[str, Any] | None:
    if not screen.get("present"):
        return None
    return {"year": screen["year"], "today": screen["today"], "days": screen["days"]}


def season(share: float) -> Colour:
    """The colour of the year `share` (0 to 1) of the way through."""
    for (a, ca), (b, cb) in zip(SEASONS, SEASONS[1:], strict=False):
        if share <= b:
            return mix(ca, cb, (share - a) / (b - a))
    return SEASONS[-1][1]


def earth(day: int, days: int) -> tuple[float, float]:
    """Where day `day` (1 for 1 January) lies on the path: the year starts nearest to you."""
    turn = 2 * math.pi * (day - 1) / days
    return SUN[0] + RX * math.sin(turn), SUN[1] + RY * math.cos(turn)


def paint_year(data: dict[str, Any], store: Any = None) -> Image.Image:
    days, today, year = data["days"], data["today"], data["year"]
    base = paint.vertical(SIZE, [(0, (4, 4, 10)), (1, (8, 7, 18))])
    rng = random.Random(year)
    layer, draw = paint.shapes()
    for _ in range(140):
        paint.disc(draw, rng.random() * SIZE, rng.random() * SIZE,
                   rng.choice((0.6, 0.8, 1.0, 1.3)), (255, 255, 255, rng.randint(40, 150)))
    base = paint.lay(base, layer)
    paint.glow(base, *SUN, 190, (255, 170, 80), 0.28, power=2.0)
    paint.glow(base, *SUN, 70, (255, 220, 160), 0.8, power=1.6)
    # The path, faint, and where each month starts.
    layer, draw = paint.shapes()
    for n in range(1, days + 1):
        paint.disc(draw, *earth(n, days), 1.0, (255, 255, 255, 40))
    first = date(year, 1, 1)
    for month in range(1, 13):
        n = (date(year, month, 1) - first).days + 1
        paint.disc(draw, *earth(n, days), 2.4, (255, 255, 255, 110))
    base = paint.lay(base, layer)
    # The days gone: a soft glow along the path, then a bead per day, nearer today brighter.
    glow = Image.new("RGB", (SIZE, SIZE), (0, 0, 0))
    lines = ImageDraw.Draw(glow)
    for n in range(1, today):
        bright = 0.25 + 0.75 * (n / today) ** 1.5
        colour = tuple(int(v * bright) for v in season((n - 1) / days))
        lines.line((*earth(n, days), *earth(n + 1, days)), fill=colour, width=14)
    base = ImageChops.add(base, glow.filter(ImageFilter.GaussianBlur(9)))
    layer, draw = paint.shapes()
    for n in range(1, today + 1):
        x, y = earth(n, days)
        age = (today - n) / today
        near = 0.55 + 0.45 * (y - (SUN[1] - RY)) / (2 * RY)  # the far side of the path dimmer
        alpha = int(255 * (0.25 + 0.75 * (1 - age) ** 1.5) * near)
        paint.disc(draw, x, y, 2.6 + 2.2 * (1 - age), (*season((n - 1) / days), alpha))
    paint.disc(draw, *SUN, 30, (255, 236, 200, 255))
    base = paint.lay(base, layer)
    paint.glow(base, *SUN, 46, (255, 250, 230), 0.6)
    # Earth, lit from the sun's side.
    ex, ey = earth(today, days)
    paint.glow(base, ex, ey, 46, season((today - 1) / days), 0.55)
    layer, draw = paint.shapes()
    paint.disc(draw, ex, ey, 17, (40, 70, 150, 255))
    towards = math.atan2(SUN[1] - ey, SUN[0] - ex)
    for k in range(12):
        f = k / 12
        paint.disc(draw, ex + math.cos(towards) * 6 * f, ey + math.sin(towards) * 6 * f,
                   17 - 11 * f, (*mix((90, 150, 255), (220, 240, 255), f), 120))
    return paint.grain(paint.lay(base, layer), year, 3)
