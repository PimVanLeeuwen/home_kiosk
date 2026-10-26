"""I, the rain radar (plan.md M27, restyled 2026-10-26): Buienradar's rain round home as a
weather map in the panels' colours. The land is our own outline, crisp at any size: Natural
Earth's 1:10m land and lakes (public domain), clipped to Buienradar's picture and simplified
to about 100 m (app/radar_coast.json); Buienradar's own map has the rain drawn into it and
showed its pixels blown up. The rain in smooth bands by its strength (Buienradar shades it
from pale lilac to deep blue), each with a fine line along its edge; dashed rings at 10, 25 and
50 km; home as a dot; the next two hours as bars along the foot. The panel lays the words on
top (desk_pieces.radar_screen).
"""

from __future__ import annotations

import io
import json
import math
from datetime import datetime
from pathlib import Path
from typing import Any

from PIL import Image, ImageChops, ImageDraw, ImageFilter

from . import paint
from .paint import SIZE, SS, Colour, hex_colour, mix
from .sources import radar

SPAN = 250  # Buienradar pixels across the panel: a zoom of 2.9
BARS_TOP, BARS_H = 604, 56
COAST = json.loads(Path(__file__).with_name("radar_coast.json").read_text())
SEA: Colour = (3, 3, 7)
LAND: Colour = (17, 16, 27)
SHORE: Colour = (100, 96, 140)
# The rain's strength (0 to 255, see `_field`) where each band starts, its colour and opacity.
BANDS: tuple[tuple[int, Colour, float], ...] = (
    (28, (34, 58, 120), 0.55), (90, (56, 112, 214), 0.72),
    (150, (110, 178, 255), 0.85), (205, (226, 238, 255), 1.0))
RINGS_KM = (10, 25, 50)
PX_PER_KM = radar.PX_PER_LAT / 111.2  # on Buienradar's picture


def inputs(screen: dict[str, Any], local: datetime) -> dict[str, Any] | None:
    if not screen.get("present") or not screen.get("stamp"):
        return None
    return {"stamp": screen["stamp"], "home": screen["home"], "rain": screen["rain"]}


def _field(data: bytes) -> Image.Image:
    """The rain's strength at Buienradar's size: 0 where dry, 40 for the lightest rain to 255
    for the heaviest (its red channel falls from 236, pale lilac, as the blue deepens)."""
    with Image.open(io.BytesIO(data)) as raw:
        rain = raw.convert("RGBA")
    present = rain.getchannel("A").point(lambda v: 255 if v > 20 else 0)
    strength = rain.getchannel("R").point(lambda v: max(0, min(255, (236 - v) * 255 // 130)))
    return ImageChops.multiply(present, strength.point(lambda v: 40 + v * 215 // 255))


def _land(home: list[float], span: tuple[float, float], size: tuple[int, int]) -> Image.Image:
    """The land (lakes left out) as a mask, drawn large and scaled down for smooth edges."""
    big = Image.new("L", (size[0] * SS, size[1] * SS), 0)
    draw = ImageDraw.Draw(big)
    x0, y0 = home[0] - span[0] / 2, home[1] - span[1] / 2
    sx, sy = size[0] * SS / span[0], size[1] * SS / span[1]
    for kind, fill in (("land", 255), ("lakes", 0)):
        for ring in COAST[kind]:
            points = [((x - x0) * sx, (y - y0) * sy)
                      for x, y in (radar.to_pixel(lat, lon) for lat, lon in ring)]
            draw.polygon(points, fill=fill)
    return big.resize(size, Image.Resampling.LANCZOS)


def _edge(mask: Image.Image) -> Image.Image:
    return ImageChops.subtract(mask.filter(ImageFilter.MaxFilter(3)),
                               mask.filter(ImageFilter.MinFilter(3)))


def _view(home: list[float], span: tuple[float, float],
          size: tuple[int, int]) -> Image.Image | None:
    """The map round home, `span` Buienradar pixels shown at `size`: land, shore, rain bands,
    and the distance rings; None until a rain layer is in."""
    if radar.FRAMES.rain is None:
        return None
    x0, y0 = home[0] - span[0] / 2, home[1] - span[1] / 2
    zoom = size[0] / span[0]
    field = _field(radar.FRAMES.rain).transform(
        size, Image.Transform.AFFINE, (1 / zoom, 0, x0, 0, 1 / zoom, y0),
        Image.Resampling.BICUBIC).filter(ImageFilter.GaussianBlur(zoom * 1.7))
    land = _land(home, span, size)
    base = paint.tint(Image.new("RGB", size, SEA), land, LAND)
    base = paint.tint(base, _edge(land), SHORE, 0.7)
    for level, colour, opacity in BANDS:
        band = field.point(lambda v, at=level: 255 if v > at else 0).filter(
            ImageFilter.GaussianBlur(0.8))
        base = paint.tint(base, band, colour, opacity)
        base = paint.tint(base, _edge(band), mix(colour, (255, 255, 255), 0.45), 0.7)
    layer = Image.new("RGBA", (size[0] * SS, size[1] * SS), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    cx, cy = size[0] / 2, size[1] / 2
    for km in RINGS_KM:
        r = km * PX_PER_KM * zoom
        for start in range(0, 360, 4):  # dashed: two degrees on, two off
            draw.arc(((cx - r) * SS, (cy - r) * SS, (cx + r) * SS, (cy + r) * SS), start,
                     start + 2, fill=(255, 255, 255, 46), width=2 * SS)
    return paint.lay(base, layer)


def _home(base: Image.Image, draw: ImageDraw.ImageDraw, cx: float, cy: float) -> None:
    paint.glow(base, cx, cy, 40, (255, 255, 255), 0.35)
    paint.disc(draw, cx, cy, 6, (255, 255, 255, 255))
    draw.ellipse(((cx - 14) * SS, (cy - 14) * SS, (cx + 14) * SS, (cy + 14) * SS),
                 outline=(255, 255, 255, 140), width=2 * SS)


def paint_radar(data: dict[str, Any], store: Any = None) -> Image.Image | None:
    base = _view(data["home"], (SPAN, SPAN), (SIZE, SIZE))
    if base is None:
        return None
    shade = paint.vertical(SIZE, [(0, (150,) * 3), (0.13, (0,) * 3), (0.72, (0,) * 3),
                                  (0.82, (230,) * 3), (1, (240,) * 3)]).convert("L")
    base = paint.tint(base, shade, (4, 4, 8))
    layer, draw = paint.shapes()
    _home(base, draw, SIZE / 2, SIZE / 2)
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
    """The radar for the Weather page as a JPEG: the same map, wider, home marked; painted
    once per frame."""
    key = (stamp, tuple(home))
    if _web["key"] == key:
        return _web["jpeg"]
    base = _view(home, WEB_SPAN, WEB_SIZE)
    if base is None:
        return None
    layer = Image.new("RGBA", (WEB_SIZE[0] * SS, WEB_SIZE[1] * SS), (0, 0, 0, 0))
    _home(base, ImageDraw.Draw(layer), WEB_SIZE[0] / 2, WEB_SIZE[1] / 2)
    out = io.BytesIO()
    paint.grain(paint.lay(base, layer), 43, 2).save(out, "JPEG", quality=86)
    _web.update(key=key, jpeg=out.getvalue())
    return _web["jpeg"]
