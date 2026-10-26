"""I, the rain radar (plan.md M27): Buienradar's radar round home, restyled in the panels'
colours: its map recoloured (the land a dark violet grey, the sea nearly black, the borders
faint), the rain over it in soft blue and white with a glow, home as a dot, and the next two
hours as bars along the foot. The panel lays the words on top (desk_pieces.radar_screen).
"""

from __future__ import annotations

import io
import math
from datetime import datetime
from typing import Any

from PIL import Image, ImageChops, ImageDraw

from . import paint
from .paint import SIZE, SS, hex_colour, mix
from .sources import radar

SPAN = 250  # Buienradar pixels across the panel: a zoom of 2.9
BARS_TOP, BARS_H = 604, 56


def inputs(screen: dict[str, Any], local: datetime) -> dict[str, Any] | None:
    if not screen.get("present") or not screen.get("stamp"):
        return None
    return {"stamp": screen["stamp"], "home": screen["home"], "rain": screen["rain"]}


def _image(data: bytes) -> Image.Image:
    with Image.open(io.BytesIO(data)) as raw:
        return raw.convert("RGBA")


def _restyle(clean: Image.Image) -> Image.Image:
    r, g, b = clean.split()
    sea = ImageChops.multiply(b.point(lambda v: 255 if v > 90 else 0),
                              g.point(lambda v: 255 if v < 70 else 0))
    border = ImageChops.multiply(r.point(lambda v: 255 if v > 140 else 0),
                                 g.point(lambda v: 255 if v > 140 else 0))
    land_tone = g.point(lambda v: max(0, min(255, (v - 100) * 2)))  # the brighter, the farther
    land = Image.merge("RGB", [land_tone.point(lambda v: 30 + v * 14 // 255),
                               land_tone.point(lambda v: 28 + v * 14 // 255),
                               land_tone.point(lambda v: 46 + v * 18 // 255)])
    out = paint.tint(land, sea, (7, 8, 15))
    return paint.tint(out, paint.soften(border, 0.6), (96, 92, 128), 0.55)


def _styled() -> Image.Image | None:
    """Buienradar's map in the panels' colours with the latest rain over it, at its own size;
    None until both are in."""
    frames = radar.FRAMES
    if frames.map is None or frames.rain is None:
        return None
    rain = _image(frames.rain)
    # The rain drawn into the map lies under the fresh rain layer: restyled as it is.
    styled = _restyle(_image(frames.map).convert("RGB")).convert("RGBA")
    # The rain: its strength as alpha, in soft blue to white, with a glow round it.
    strength = rain.getchannel("A").point(lambda v: min(255, v * 3 // 2))
    colour = Image.merge("RGB", [strength.point(lambda v: 120 + v * 120 // 255),
                                 strength.point(lambda v: 170 + v * 80 // 255),
                                 Image.new("L", rain.size, 255)])
    glow = paint.soften(strength, 6).point(lambda v: v // 2)
    styled = Image.composite(Image.new("RGBA", rain.size, (90, 140, 255, 255)), styled, glow)
    return Image.composite(colour.convert("RGBA"), styled, strength)


def paint_radar(data: dict[str, Any], store: Any = None) -> Image.Image | None:
    styled = _styled()
    if styled is None:
        return None
    # Round home, scaled up to the panel.
    hx, hy = data["home"]
    half = SPAN / 2
    box = (round(hx - half), round(hy - half), round(hx + half), round(hy + half))
    base = styled.crop(box).resize((SIZE, SIZE), Image.Resampling.BICUBIC).convert("RGB")
    shade = paint.vertical(SIZE, [(0, (150,) * 3), (0.13, (0,) * 3), (0.72, (0,) * 3),
                                  (0.82, (230,) * 3), (1, (240,) * 3)]).convert("L")
    base = paint.tint(base, shade, (5, 5, 9))
    layer, draw = paint.shapes()
    cx = cy = SIZE / 2
    paint.glow(base, cx, cy, 40, (255, 255, 255), 0.4)
    paint.disc(draw, cx, cy, 7, (255, 255, 255, 255))
    draw.ellipse(((cx - 15) * SS, (cy - 15) * SS, (cx + 15) * SS, (cy + 15) * SS),
                 outline=(255, 255, 255, 150), width=2 * SS)
    # The next two hours, one bar per five minutes, as on the Clock.
    points = data["rain"]
    step = (SIZE - 72) / max(1, len(points))
    for i, mm in enumerate(points):
        if mm < radar.WET_MM:
            continue
        share = math.sqrt(min(mm, 3.0)) / math.sqrt(3.0)
        c = mix(hex_colour("5f86c4"), hex_colour("c4dcff"), share)
        h = 6 + share * (BARS_H - 6)
        x1 = 36 + i * step + 2
        draw.rounded_rectangle((x1 * SS, (BARS_TOP + BARS_H - h) * SS, (x1 + step - 4) * SS,
                                (BARS_TOP + BARS_H) * SS), radius=3 * SS, fill=(*c, 255))
    return paint.grain(paint.lay(base, layer), 43, 2)


# The hub's Weather page (plan.md M27, Q): a wider view round home, 16 by 10.
WEB_SPAN, WEB_SIZE = (320, 200), (960, 600)
_web: dict[str, Any] = {"key": None, "jpeg": None}


def web_picture(home: list[float], stamp: str | None) -> bytes | None:
    """The radar for the Weather page as a JPEG: the restyled map and rain round home, home
    marked; painted once per frame."""
    key = (stamp, tuple(home))
    if _web["key"] == key:
        return _web["jpeg"]
    styled = _styled()
    if styled is None:
        return None
    hx, hy = home
    w, h = WEB_SPAN
    box = (round(hx - w / 2), round(hy - h / 2), round(hx + w / 2), round(hy + h / 2))
    base = styled.crop(box).resize(WEB_SIZE, Image.Resampling.BICUBIC).convert("RGB")
    layer = Image.new("RGBA", (WEB_SIZE[0] * SS, WEB_SIZE[1] * SS), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    cx, cy = WEB_SIZE[0] / 2, WEB_SIZE[1] / 2
    paint.glow(base, cx, cy, 40, (255, 255, 255), 0.4)
    paint.disc(draw, cx, cy, 7, (255, 255, 255, 255))
    draw.ellipse(((cx - 15) * SS, (cy - 15) * SS, (cx + 15) * SS, (cy + 15) * SS),
                 outline=(255, 255, 255, 150), width=2 * SS)
    out = io.BytesIO()
    paint.grain(paint.lay(base, layer), 43, 2).save(out, "JPEG", quality=86)
    _web.update(key=key, jpeg=out.getvalue())
    return _web["jpeg"]
