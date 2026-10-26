"""J, your week (plan.md M27, made into a landscape on 2026-10-26): the coming days as one
scene. Each day has its own sky across the top, blending into the next (a sun on a clear day,
layered clouds, slanting rain as heavy as its chance, snow, a bolt); the week's highs are a
mountain ridge, warm where the days are warm and cool where they are cold, with a light rim;
the lows a darker range in front. Today stands in a soft beam of light, and the days' events
are small lanterns at the foot. The panel lays the names and temperatures on top
(desk_pieces.week_screen, whose columns and ridges this shares)."""

from __future__ import annotations

import math
import random
from datetime import datetime
from typing import Any

from PIL import Image, ImageChops, ImageDraw

from . import paint
from .desk_pieces import ridge_high, ridge_low, week_x
from .paint import SIZE, SS, Colour, hex_colour, mix

WHITE: Colour = (255, 255, 255)
WARM: Colour = (255, 168, 92)
COOL: Colour = (110, 128, 230)
LANTERNS = 676  # under the rain chances (y 640), above the panel's page dots
# A day's sky by its kind: (top, middle, at the ridge).
SKIES: dict[str, tuple[Colour, Colour, Colour]] = {
    "sun": ((14, 34, 86), (52, 112, 200), (150, 196, 245)),
    "partly": ((18, 32, 70), (60, 100, 170), (140, 170, 214)),
    "cloud": ((22, 26, 38), (62, 70, 90), (118, 126, 146)),
    "rain": ((16, 20, 32), (46, 58, 82), (92, 108, 136)),
    "snow": ((30, 36, 54), (100, 114, 146), (190, 202, 226)),
    "thunder": ((18, 12, 34), (58, 40, 96), (110, 86, 150)),
    "fog": ((34, 36, 44), (96, 100, 112), (150, 154, 166)),
}


def inputs(screen: dict[str, Any], local: datetime) -> dict[str, Any] | None:
    if not screen.get("present"):
        return None
    return {"days": screen["days"], "warmest": screen["warmest"], "coldest": screen["coldest"]}


def sky_of(code: int | None) -> str:
    """The WMO code as one of the skies."""
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


def _across(colours: list[list[Colour]], height: int) -> Image.Image:
    """Rows of one colour per day, blended smoothly across the week and down the rows."""
    small = Image.new("RGB", (len(colours[0]), len(colours)))
    for y, row in enumerate(colours):
        for x, c in enumerate(row):
            small.putpixel((x, y), c)
    # Half a column of margin either side, so the first and last days are not squeezed.
    wide = small.resize((len(colours[0]) * 64, height), Image.Resampling.BICUBIC)
    margin = 32 * SIZE // (len(colours[0]) * 64 - 64)
    return wide.resize((SIZE + 2 * margin, height), Image.Resampling.BICUBIC).crop(
        (margin, 0, margin + SIZE, height))


def _rough(line: list[tuple[float, float]], seed: int, amount: float) -> list[tuple[float, float]]:
    """The line with a little terrain on it: seeded bumps, more where it is high."""
    rng = random.Random(seed)
    phases = [rng.uniform(0, 6.3) for _ in range(3)]
    return [(x, y + amount * (0.6 * math.sin(x / 23 + phases[0]) + 0.3 * math.sin(x / 9 + phases[1])
                              + 0.2 * math.sin(x / 4.3 + phases[2]))) for x, y in line]


def _curve(points: list[tuple[float, float]]) -> list[tuple[float, float]]:
    """A smooth line through the days' points, out to both edges of the screen."""
    pts = [(-40.0, points[0][1])] + points + [(SIZE + 40.0, points[-1][1])]
    out = []
    for i in range(len(pts) - 1):
        p0, p1 = pts[max(0, i - 1)], pts[i]
        p2, p3 = pts[i + 1], pts[min(len(pts) - 1, i + 2)]
        for s in range(12):
            t = s / 12
            x = 0.5 * (2 * p1[0] + (-p0[0] + p2[0]) * t + (2 * p0[0] - 5 * p1[0] + 4 * p2[0]
                                                            - p3[0]) * t * t
                       + (-p0[0] + 3 * p1[0] - 3 * p2[0] + p3[0]) * t ** 3)
            y = 0.5 * (2 * p1[1] + (-p0[1] + p2[1]) * t + (2 * p0[1] - 5 * p1[1] + 4 * p2[1]
                                                            - p3[1]) * t * t
                       + (-p0[1] + 3 * p1[1] - 3 * p2[1] + p3[1]) * t ** 3)
            out.append((x, y))
    out.append(pts[-1])
    return out


def _range(base: Image.Image, line: list[tuple[float, float]], fill: Image.Image,
           rim: Colour) -> Image.Image:
    """A mountain range: everything under `line`, filled with `fill`, with a light rim."""
    mask = Image.new("L", (SIZE * SS, SIZE * SS), 0)
    ImageDraw.Draw(mask).polygon([(x * SS, y * SS) for x, y in line]
                                 + [(SIZE * SS, SIZE * SS), (0, SIZE * SS)], fill=255)
    mask = mask.resize((SIZE, SIZE), Image.Resampling.LANCZOS)
    out = Image.composite(fill, base, mask)
    edge = ImageChops.subtract(mask, ImageChops.offset(mask, 0, 3))
    return paint.tint(out, paint.soften(edge, 0.8), rim, 0.9)


def _cloud(draw: ImageDraw.ImageDraw, x: float, y: float, width: float, colour: Colour,
           rng: random.Random) -> None:
    """A soft cloud mass: overlapping puffs on a flat base, lighter on top."""
    h = width * 0.32
    draw.rounded_rectangle(((x - width / 2) * SS, (y - h * 0.4) * SS, (x + width / 2) * SS,
                            (y + h * 0.4) * SS), radius=h * 0.4 * SS, fill=(*colour, 230))
    for k in range(4):
        px = x - width / 2 + width * (k + 0.5) / 4 + rng.uniform(-6, 6)
        r = h * rng.uniform(0.5, 0.8) * (1.15 if k in (1, 2) else 0.85)
        paint.disc(draw, px, y - h * 0.25, r, (*mix(colour, WHITE, 0.12), 230))


def _weather(draw: ImageDraw.ImageDraw, base: Image.Image, x: float, ridge: float,
             sky: str, rain: int, rng: random.Random) -> None:
    """The day's weather in its own piece of sky, above its peak."""
    half, top = 44, 150
    if sky in ("sun", "partly"):
        sx, sy = x + (16 if sky == "partly" else 0), top - 6
        paint.glow(base, sx, sy, 130, (255, 206, 140), 0.5, power=2.2)
        paint.glow(base, x, ridge, 90, (255, 190, 120), 0.35)  # sunlight on the ridge below
        paint.disc(draw, sx, sy, 20, (255, 238, 205, 255))
    if sky in ("partly", "cloud", "rain", "snow", "thunder"):
        colour = {"partly": (214, 220, 236), "snow": (214, 220, 236),
                  "thunder": (96, 84, 130)}.get(sky, (128, 136, 158))
        _cloud(draw, x - 6, top + 12, 74, mix(colour, (0, 0, 0), 0.15), rng)
        _cloud(draw, x + 8, top + 26, 62, colour, rng)
    if sky in ("rain", "thunder") or rain >= 40:
        for _ in range(8 + rain // 5):  # heavier for a likelier rain, falling to the ridge
            rx = x + rng.uniform(-half, half)
            ry = rng.uniform(top + 40, ridge - 30)
            length = rng.uniform(12, 22)
            draw.line((rx * SS, ry * SS, (rx - length * 0.3) * SS, (ry + length) * SS),
                      fill=(160, 196, 255, rng.randrange(90, 190)), width=2 * SS)
    if sky == "snow":
        for _ in range(26):
            paint.disc(draw, x + rng.uniform(-half, half), rng.uniform(top + 40, ridge - 20),
                       rng.uniform(1.4, 3.0), (245, 248, 255, 220))
    if sky == "thunder":
        bx, by = x - 2, top + 40
        draw.polygon([((bx + 6) * SS, by * SS), ((bx - 7) * SS, (by + 26) * SS),
                      ((bx + 2) * SS, (by + 26) * SS), ((bx - 7) * SS, (by + 50) * SS),
                      ((bx + 13) * SS, (by + 19) * SS), ((bx + 3) * SS, (by + 19) * SS)],
                     fill=(255, 226, 120, 255))
        paint.glow(base, bx, by + 24, 60, (210, 180, 255), 0.4)


def _haze(base: Image.Image, line: list[tuple[float, float]], depth: int, colour: Colour,
          strength: float, seed: int) -> Image.Image:
    """A band of drifting haze lying along `line`, fading out over `depth` below it."""
    band = Image.new("L", (SIZE, SIZE), 0)
    bd = ImageDraw.Draw(band)
    for step in range(depth):
        bd.line([(x, y + step) for x, y in line], fill=round(255 * (1 - step / depth) ** 1.5))
    drift = paint.levels(paint.fbm(SIZE, SIZE, seed, 120, stretch=3.0), 70, 210)
    band = ImageChops.multiply(paint.soften(band, 6), drift)
    return paint.tint(base, band, colour, strength)


def _cap(base: Image.Image, ridge: list[tuple[float, float]], x: float) -> Image.Image:
    """Snow on the peak at x: the ridge's top few pixels there, white."""
    cap = Image.new("L", (SIZE, SIZE), 0)
    near = [(px, py) for px, py in ridge if abs(px - x) < 38]
    ImageDraw.Draw(cap).polygon(near + [(px, py + 16 - abs(px - x) * 0.35) for px, py in
                                        reversed(near)], fill=230)
    return paint.tint(base, paint.soften(cap, 1.2), (240, 244, 255))


def paint_week(data: dict[str, Any], store: Any = None) -> Image.Image:
    days, warmest, coldest = data["days"], data["warmest"], data["coldest"]
    skies = [SKIES[sky_of(d.get("code"))] for d in days]
    base = _across([[s[0] for s in skies], [s[1] for s in skies], [s[2] for s in skies]], SIZE)
    rng = random.Random(int(warmest * 10 + coldest))
    highs = [(week_x(i), ridge_high(d["high"], warmest, coldest)) for i, d in enumerate(days)]
    lows = [(week_x(i), ridge_low(d["low"], warmest, coldest)) for i, d in enumerate(days)]

    # Each day's weather in its sky, high above its peak.
    layer, draw = paint.shapes()
    for i, d in enumerate(days):
        _weather(draw, base, week_x(i), highs[i][1], sky_of(d.get("code")), d.get("rain") or 0,
                 rng)
    base = paint.lay(base, layer)

    # Today in a beam of light, from the top down to the ridges.
    beam = paint.vertical(SIZE, [(0, (90,) * 3), (0.7, (40,) * 3), (1, (0,) * 3)]).convert("L")
    column = Image.new("L", (SIZE, SIZE), 0)
    x0 = week_x(0)
    ImageDraw.Draw(column).rectangle((x0 - 40, 0, x0 + 40, SIZE), fill=255)
    beam = ImageChops.multiply(paint.soften(column, 22), beam)
    base = paint.tint(base, beam, WHITE)

    # Fog: soft banks of mist lying in the day's sky and over its ridge.
    for i, d in enumerate(days):
        if sky_of(d.get("code")) == "fog":
            bank = Image.new("L", (SIZE, SIZE), 0)
            fd = ImageDraw.Draw(bank)
            for k in range(9):  # wisps of mist, drifting, thicker towards the ground
                y = highs[i][1] - 130 + k * 17 + rng.uniform(-5, 5)
                cx, half = week_x(i) + rng.uniform(-22, 22), rng.uniform(30, 64)
                fd.ellipse((cx - half, y - 7, cx + half, y + 7), fill=70 + 9 * k)
            base = paint.tint(base, paint.soften(bank, 9), (226, 230, 240))

    # The ranges: the highs behind, warm or cool by the day, with a little terrain; a misty
    # range between; the lows in front, darker.
    warmth = [(d["high"] - coldest) / max(4.0, warmest - coldest) for d in days]
    back = _across([[mix(COOL, WARM, w) for w in warmth],
                    [mix(mix(COOL, WARM, w), (40, 18, 60), 0.55) for w in warmth],
                    [(12, 8, 24)] * len(days)], SIZE)
    ridge = _rough(_curve(highs), 7, 5)
    glow_line = Image.new("L", (SIZE, SIZE), 0)
    ImageDraw.Draw(glow_line).line(ridge, fill=255, width=6)
    base = paint.tint(base, paint.soften(glow_line, 10), (255, 214, 170), 0.55)
    rock = paint.levels(paint.fbm(SIZE, SIZE, 5, 90, stretch=2.2), 60, 200)
    back = Image.composite(back, paint.tint(back, rock, (0, 0, 0), 0.45), rock)
    base = _range(base, ridge, back, (255, 236, 210))
    for i, d in enumerate(days):  # snow on the peaks of the cold days
        if d["high"] <= 3:
            base = _cap(base, ridge, week_x(i))
    base = _haze(base, [(x, y + 34) for x, y in ridge], 70, (196, 178, 236), 0.42, 21)
    middle = [(x, (y1 + y2) / 2 + 10) for (x, y1), (_, y2) in zip(highs, lows, strict=True)]
    mist = _across([[mix((96, 78, 150), (150, 96, 120), w) for w in warmth],
                    [(44, 32, 78)] * len(days), [(14, 10, 26)] * len(days)], SIZE)
    base = _range(base, _rough(_curve(middle), 11, 4), mist, (150, 136, 200))
    base = _haze(base, [(x, y - 6) for x, y in _curve(lows)], 60, (120, 104, 180), 0.35, 23)
    front = _across([[mix((70, 54, 128), (128, 76, 96), w) for w in warmth],
                     [(26, 18, 46)] * len(days), [(6, 4, 12)] * len(days)], SIZE)
    base = _range(base, _rough(_curve(lows), 13, 4), front, (190, 178, 240))

    layer, draw = paint.shapes()
    for x, y in highs:  # each day's peak a small light
        paint.disc(draw, x, y, 4, (255, 246, 230, 255))
    for i, d in enumerate(days):  # the day's events as lanterns at the foot
        for k, colour in enumerate(d.get("events") or []):
            ex = week_x(i) + (k - (len(d["events"]) - 1) / 2) * 16
            paint.glow(base, ex, LANTERNS, 16, hex_colour(colour), 0.6)
            paint.disc(draw, ex, LANTERNS, 4.5, (*hex_colour(colour), 255))
    base = paint.lay(base, layer)
    for x, y in highs:
        paint.glow(base, x, y, 26, (255, 230, 200), 0.35)
    return paint.grain(base, 41, 3)
