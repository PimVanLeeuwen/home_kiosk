"""The Clock's background (plan.md M27, the lifted Clock): the sky of the moment with
its clouds, the sun or the moon on its arc with the light around it, the stars on a
clear night, the horizon, and the coming rain as bars under it. The panel lays the
time and the words on top and lets rain fall while it rains.

The geometry is the panel's (panels/firmware/main/screen_clock.c): the horizon at
476, the arc from (40, 476) over (360, 250) to (680, 476), the bars under the
horizon. Without this picture the panel draws a plainer sky of its own.
"""

from __future__ import annotations

import math
import random
from datetime import datetime
from typing import Any

from PIL import Image, ImageChops, ImageDraw

from . import paint
from .paint import SIZE, SS, Colour, hex_colour, mix

HORIZON = 476
MARGIN = 36
LONGEST, SHORTEST, TOP_MM, WET_MM = 72, 8, 3.0, 0.1
WHITE: Colour = (255, 255, 255)
BLACK: Colour = (0, 0, 0)
SUN: Colour = (255, 231, 194)
MOON: Colour = (227, 231, 255)
DRIFT_PX = 1.5  # how far the clouds move between repaints (every 3 minutes)

# How much of the sky the clouds cover, by the weather; overcast skies are greyer.
COVER = {"clear": 0.0, "partly": 0.42, "cloudy": 0.85, "fog": 0.7, "rain": 0.9,
         "thunder": 0.95, "snow": 0.85}


def inputs(screen: dict[str, Any], local: datetime) -> dict[str, Any] | None:
    """What the picture shows, from the clock screen at `local` (the configured zone):
    changes to these, and only these, paint a new one. The sun's place and the clouds'
    drift move in 3-minute steps."""
    sky = screen.get("horizon")
    if not sky:
        return None
    minute = local.hour * 60 + local.minute
    rain = screen.get("rain") or []
    return {
        "top": sky["top"], "mid": sky["mid"], "low": sky["low"],
        "body": sky["body"], "at": round(sky["at"] / 5) * 5,
        "moon": round(sky["moon"] / 20) * 20, "veiled": sky["veiled"], "stars": sky["stars"],
        "weather": sky.get("weather") or "partly",
        "rain": [round(mm, 1) for mm in rain] if screen.get("wet") else [],
        "stale": bool(screen.get("stale")),
        "day": local.date().toordinal(), "drift": minute // 3,
    }


def on_arc(t: float) -> tuple[float, float]:
    x0, y0, cx, cy, x1, y1 = 40, HORIZON, 360, 250, 680, HORIZON
    u = 1 - t
    return u * u * x0 + 2 * u * t * cx + t * t * x1, u * u * y0 + 2 * u * t * cy + t * t * y1


def _stars(base: Image.Image, seed: int) -> None:
    rng = random.Random(seed)
    layer, draw = paint.shapes()
    for _ in range(170):
        x, y = rng.uniform(0, SIZE), (HORIZON - 30) * rng.random() ** 1.4  # fewer low down
        bright = rng.random() ** 2.4
        alpha = round(70 + 170 * bright * (1 - y / HORIZON * 0.6))
        paint.disc(draw, x, y, 0.6 + 1.3 * bright, (235, 238, 255, alpha))
        if bright > 0.93:
            paint.glow(base, x, y, 6, (150, 165, 255), 0.3)
    base.paste(paint.lay(base, layer))


def _puffs(draw: ImageDraw.ImageDraw, x: float, base: float, width: float, height: float,
           rng: random.Random) -> None:
    """One cloud on a mask at twice the size: a flat-bottomed body with round puffs on top."""
    r = height * 0.42
    draw.rounded_rectangle(((x - width / 2) * SS, (base - 2 * r) * SS, (x + width / 2) * SS,
                            base * SS), radius=r * SS, fill=255)
    n = max(2, round(width / (height * 0.8)))
    for i in range(n):
        px = x - width / 2 + r + (width - 2 * r) * (i + rng.uniform(-0.2, 0.2)) / max(1, n - 1)
        pr = height * rng.uniform(0.38, 0.62) * (1.15 if 0 < i < n - 1 else 0.85)
        py = base - 2 * r + pr * 0.35
        draw.ellipse(((px - pr) * SS, (py - pr) * SS, (px + pr) * SS, (py + pr) * SS), fill=255)


def _layer(sky: Image.Image, mask: Image.Image, colour: Colour, night: bool) -> Image.Image:
    """A layer of clouds over the sky: a soft shadow under it, its body shading from a lit
    top to a darker base, and a fine light edge along its top."""
    mask = mask.resize(sky.size, Image.Resampling.LANCZOS)
    shadow = paint.soften(ImageChops.offset(mask, 0, 9), 8).point(lambda v: v * 70 // 255)
    out = paint.tint(sky, shadow, mix(colour, BLACK, 0.55))
    body = paint.vertical(HORIZON, [(0, mix(colour, WHITE, 0.08)), (1, mix(colour, BLACK, 0.2))])
    out = paint.tint(out, mask, body)
    edge = ImageChops.subtract(mask, ImageChops.offset(mask, 0, 3))
    return paint.tint(out, edge, mix(colour, WHITE, 0.12 if night else 0.35), 0.8)


def _clouds(sky: Image.Image, top: Colour, mid: Colour, low: Colour, weather: str,
            night: bool, seed: int, drift: int) -> Image.Image:
    """Clouds as clean, layered shapes (the owner's wish, 2026-10-25: crisp, not smeared):
    a few apart on a partly cloudy day; banks over each other, the far ones higher and
    darker, on an overcast one. Each layer drifts at its own pace, the near ones faster."""
    cover = COVER.get(weather, 0.42)
    if cover <= 0:
        return sky
    grey = weather in ("rain", "thunder", "cloudy", "fog", "snow")
    lit = mix(low, WHITE, 0.12 if night else 0.5)
    if grey:
        lit = mix(lit, (128, 134, 148) if not night else (52, 58, 74), 0.55)
    shade = mix(mid, BLACK, 0.25)
    moved = drift * DRIFT_PX
    out = sky
    if cover > 0.6:
        # Banks: (bottom, puff height, spacing, pace, colour from the far shade to the lit).
        banks = [(175, 72, 150, 0.4, 0.15), (315, 88, 175, 0.65, 0.45), (462, 104, 205, 1.0, 0.85)]
    else:
        banks = [(0, 0, 250, 0.7, 0.85)]  # apart: placed one by one below
    for bank, (bottom, height, spacing, pace, light) in enumerate(banks):
        mask = Image.new("L", (SIZE * SS, HORIZON * SS), 0)
        draw = ImageDraw.Draw(mask)
        offset = moved * pace
        first = math.floor(offset / spacing)
        for k in range(-2, SIZE // spacing + 3):
            index = first + k
            rng = random.Random(seed * 1009 + bank * 97 + index)
            x = index * spacing - offset + rng.uniform(-0.2, 0.2) * spacing
            if cover > 0.6:
                _puffs(draw, x, bottom + rng.uniform(-18, 14), spacing * rng.uniform(1.1, 2.0),
                       height * rng.uniform(0.72, 1.3), rng)
            elif rng.random() < 0.55:
                # Under the words: never behind the time, the date or the weather, where a
                # light cloud would take the white text's contrast.
                h = rng.uniform(40, 60)
                _puffs(draw, x, rng.uniform(370, 440), h * rng.uniform(2.6, 4.2), h, rng)
        out = _layer(out, mask, mix(shade, lit, light), night)
    return out


def _body(base: Image.Image, data: dict[str, Any], top: Colour, mid: Colour, low: Colour) -> None:
    x, y = on_arc(data["at"] / 1000)
    veiled = data["veiled"]
    if data["body"] == "sun":
        paint.glow(base, x, y, 240, (255, 196, 140), 0.18 if veiled else 0.3, power=2.8)
        paint.glow(base, x, y, 70, (255, 222, 180), 0.25 if veiled else 0.45)
        layer, draw = paint.shapes()
        paint.disc(draw, x, y, 26, (*SUN, 150 if veiled else 255))
        base.paste(paint.lay(base, layer))
        return
    paint.glow(base, x, y, 120, (190, 200, 255), 0.18 if veiled else 0.3)
    # The lit part: the disc less a disc shifted by how much is lit (left while waxing,
    # right while waning), as on the panel; the dark part keeps a faint earthshine.
    f = data["moon"] / 1000
    lit = (1 - math.cos(2 * math.pi * f)) / 2
    disc, d1 = paint.shapes()
    paint.disc(d1, x, y, 21, (255, 255, 255, 255))
    shadow, d2 = paint.shapes()
    if lit < 0.97:
        sx = x + 2 * 21 * lit * (-1 if f < 0.5 else 1)
        paint.disc(d2, sx, y, 22.5, (255, 255, 255, 255))
    whole = disc.getchannel("A")
    lit_part = ImageChops.subtract(whole, shadow.getchannel("A"))
    layer = Image.new("RGBA", whole.size, (*MOON, 0))
    layer.putalpha(ImageChops.add(lit_part.point(lambda v: v * (150 if veiled else 255) // 255),
                                  whole.point(lambda v: v * 22 // 255)))
    # Its seas: a few soft darker patches on the lit part.
    seas, d3 = paint.shapes()
    rng = random.Random(7)
    for _ in range(6):
        px, py, pr = rng.uniform(-11, 11), rng.uniform(-11, 11), rng.uniform(3, 7)
        if math.hypot(px, py) + pr < 20:
            paint.disc(d3, x + px, y + py, pr, (176, 182, 210, 60))
    seas.putalpha(ImageChops.multiply(seas.getchannel("A"), lit_part))
    base.paste(paint.lay(paint.lay(base, layer), seas))


def _arc_and_horizon(base: Image.Image, low: Colour) -> None:
    layer, draw = paint.shapes()
    for i in range(1, 40):
        x, y = on_arc(i / 40)
        paint.disc(draw, x, y, 2, (255, 255, 255, 40))
    line = mix(low, WHITE, 0.35)
    draw.rectangle((0, HORIZON * SS - SS, SIZE * SS, HORIZON * SS + SS), fill=(*line, 160))
    base.paste(paint.lay(base, layer))


def _bars(base: Image.Image, rain: list[float], stale: bool) -> None:
    if not rain:
        return
    layer, draw = paint.shapes()
    step = (SIZE - 2 * MARGIN) / len(rain)
    for i, mm in enumerate(rain):
        if mm < WET_MM:
            continue
        share = math.sqrt(min(mm, TOP_MM)) / math.sqrt(TOP_MM)
        colour = mix(hex_colour("5f86c4"), hex_colour("c4dcff"), share)
        x1, x2 = MARGIN + i * step + 3, MARGIN + (i + 1) * step - 3
        y1 = HORIZON + 4
        y2 = y1 + SHORTEST + share * (LONGEST - SHORTEST)
        draw.rounded_rectangle((x1 * SS, y1 * SS, x2 * SS, y2 * SS), radius=4 * SS,
                               fill=(*colour, 128 if stale else 255))
        # A brighter top, as if lit from the sky.
        draw.rounded_rectangle((x1 * SS, y1 * SS, x2 * SS, (y1 + 4) * SS), radius=3 * SS,
                               fill=(*mix(colour, WHITE, 0.45), 128 if stale else 255))
    base.paste(paint.lay(base, layer))


def paint_clock(data: dict[str, Any], store: Any = None) -> Image.Image:
    top, mid, low = (hex_colour(data[k]) for k in ("top", "mid", "low"))
    night = data["body"] == "moon"
    seed = data["day"]
    sky = paint.vertical(HORIZON, [(0, top), (0.55, mid), (1, low)])
    # The haze along the horizon: the sky a little lighter just above it.
    haze = paint.vertical(HORIZON, [(0, BLACK), (0.7, BLACK), (1, mix(low, WHITE, 0.25))])
    sky = ImageChops.add(sky, ImageChops.multiply(haze, Image.new("RGB", sky.size, (90, 90, 90))))
    if data["stars"]:
        _stars(sky, seed)
    _body(sky, data, top, mid, low)
    sky = _clouds(sky, top, mid, low, data["weather"], night, seed, data["drift"])

    base = Image.new("RGB", (SIZE, SIZE), BLACK)
    base.paste(sky, (0, 0))
    fade = 90 / (SIZE - HORIZON)
    ground = paint.vertical(SIZE - HORIZON, [(0, mix(low, BLACK, 0.86)), (fade, BLACK), (1, BLACK)])
    base.paste(ground, (0, HORIZON))
    _arc_and_horizon(base, low)
    _bars(base, data["rain"], data["stale"])
    return paint.grain(base, seed, 3)
