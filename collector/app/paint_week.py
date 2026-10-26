"""J, your week (plan.md M27): seven columns, each a glowing bar from the day's low to its
high, warm at the top and cool below, joined by a line through the highs; the day's sky as
a small icon; a dot per event in its calendar's colour; today on a pane of glass. The panel
lays the names, the temperatures and the chances of rain on top (desk_pieces.week_screen,
whose columns and rows this shares)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from PIL import Image, ImageDraw

from . import paint
from .desk_pieces import WEEK_BOTTOM, WEEK_TOP, week_x, week_y
from .paint import SIZE, SS, Colour, hex_colour, mix

WARM: Colour = (255, 184, 107)
COOL: Colour = (138, 180, 255)
ICON_Y = 152


def inputs(screen: dict[str, Any], local: datetime) -> dict[str, Any] | None:
    if not screen.get("present"):
        return None
    return {"days": screen["days"], "warmest": screen["warmest"], "coldest": screen["coldest"]}


def _sky(code: int | None) -> str:
    """The WMO code as one of the icons."""
    if code is None or code <= 1:
        return "sun"
    if code == 2:
        return "partly"
    if code == 3:
        return "cloud"
    if code in (45, 48):
        return "fog"
    if code >= 95:
        return "thunder"
    if 71 <= code <= 77 or code in (85, 86):
        return "snow"
    return "rain"


def _icon(draw: ImageDraw.ImageDraw, x: float, y: float, sky: str) -> None:
    sun, cloud = (255, 205, 120, 255), (200, 206, 224, 255)
    if sky in ("sun", "partly"):
        sx, sy = (x - 8, y - 8) if sky == "partly" else (x, y)
        paint.disc(draw, sx, sy, 12 if sky == "partly" else 14, sun)
    if sky != "sun":
        for dx, dy, r in ((-10, 4, 10), (2, -2, 13), (13, 5, 9)):
            paint.disc(draw, x + dx, y + dy, r, cloud)
        draw.rounded_rectangle(((x - 20) * SS, (y + 2) * SS, (x + 22) * SS, (y + 14) * SS),
                               radius=6 * SS, fill=cloud)
    if sky == "rain":
        for dx in (-10, 0, 10):
            draw.line(((x + dx) * SS, (y + 20) * SS, (x + dx - 4) * SS, (y + 30) * SS),
                      fill=(130, 175, 255, 255), width=3 * SS)
    if sky == "snow":
        for dx in (-10, 0, 10):
            paint.disc(draw, x + dx, y + 25, 2.6, (240, 244, 255, 255))
    if sky == "thunder":
        draw.polygon([((x + 2) * SS, (y + 14) * SS), ((x - 6) * SS, (y + 28) * SS),
                      ((x + 1) * SS, (y + 28) * SS), ((x - 4) * SS, (y + 40) * SS),
                      ((x + 8) * SS, (y + 24) * SS), ((x + 1) * SS, (y + 24) * SS)],
                     fill=(255, 220, 110, 255))
    if sky == "fog":
        for dy in (20, 28):
            draw.line(((x - 18) * SS, (y + dy) * SS, (x + 18) * SS, (y + dy) * SS),
                      fill=(190, 196, 214, 200), width=3 * SS)


def paint_week(data: dict[str, Any], store: Any = None) -> Image.Image:
    days, warmest, coldest = data["days"], data["warmest"], data["coldest"]
    base = Image.new("RGB", (SIZE, SIZE), (0, 0, 0))
    paint.glow(base, SIZE - 60, -40, 420, (124, 108, 242), 0.18, power=2.4)
    paint.glow(base, 360, (WEEK_TOP + WEEK_BOTTOM) / 2, 380, WARM, 0.08)
    layer, draw = paint.shapes()
    # Today on a pane of glass.
    x0 = week_x(0)
    draw.rounded_rectangle(((x0 - 42) * SS, 66 * SS, (x0 + 42) * SS, 650 * SS), radius=22 * SS,
                           fill=(255, 255, 255, 14), outline=(255, 255, 255, 40), width=SS)
    tops = []
    for i, d in enumerate(days):
        x = week_x(i)
        top, bottom = week_y(d["high"], warmest, coldest), week_y(d["low"], warmest, coldest)
        tops.append((x, top))
        _icon(draw, x, ICON_Y, _sky(d.get("code")))
        # The bar, warm to cool, drawn as stacked slices for its gradient.
        for y in range(top, bottom + 1):
            t = (y - WEEK_TOP) / max(1, WEEK_BOTTOM - WEEK_TOP)
            c = mix(WARM, COOL, t)
            draw.rounded_rectangle(((x - 9) * SS, y * SS, (x + 9) * SS, (y + 1) * SS),
                                   radius=0, fill=(*c, 235))
        for y in (top, bottom):  # round ends, in their colours
            t = (y - WEEK_TOP) / max(1, WEEK_BOTTOM - WEEK_TOP)
            paint.disc(draw, x, y, 9, (*mix(WARM, COOL, t), 235))
        for k, colour in enumerate(d.get("events") or []):
            paint.disc(draw, x + (k - (len(d["events"]) - 1) / 2) * 14, 616, 4.5,
                       (*hex_colour(colour), 255))
    # The line through the highs.
    draw.line([(x * SS, y * SS) for x, y in tops], fill=(255, 225, 180, 200), width=2 * SS,
              joint="curve")
    for x, y in tops:
        paint.disc(draw, x, y, 4, (255, 240, 220, 255))
    base = paint.lay(base, layer)
    for i, d in enumerate(days):  # a soft glow round each bar
        x = week_x(i)
        mid = (week_y(d["high"], warmest, coldest) + week_y(d["low"], warmest, coldest)) / 2
        paint.glow(base, x, mid, 46, WARM, 0.12)
    return paint.grain(base, 41, 3)
