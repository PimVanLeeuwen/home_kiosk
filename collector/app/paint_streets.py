"""D, your streets (plan.md M28, step 5): the home area at night from its own OpenStreetMap
shapes (app/sources/streets.py), streets as faint silver threads, the water dark with a sheen, the
parks a deeper shade; over it every route of the year there as light that adds up, so the streets
run most glow from ember to white; today's run traced on top. The panel runs a light along
today's route (screen_piece.c) and lays the words. `town` also draws A's streets (app/paint_run.py).
"""

from __future__ import annotations

import io
import math
from datetime import datetime
from typing import Any

from PIL import Image, ImageChops, ImageDraw

from . import paint
from .paint import SIZE, Colour
from .sources import runs, streets

# The panel's picture: the map fills it; the words sit on the dark band at the top.
MAP_BOX = (0, 150, 720, 720)
EMBER: Colour = (150, 52, 24)
AMBER: Colour = (255, 168, 92)
WHITE_HOT: Colour = (255, 244, 222)


class Frame:
    """Latitude and longitude onto a picture, north up: the bounds cover the box (cropped), or with
    `fit` lie inside it, which is how app/desk_running.py's `project` places A's route."""

    def __init__(self, bounds: tuple[float, float, float, float], box: tuple[int, int, int, int],
                 fit: bool = False):
        south, west, north, east = bounds
        self.squeeze = math.cos(math.radians((south + north) / 2))
        x1, y1, x2, y2 = box
        span_x, span_y = max((east - west) * self.squeeze, 1e-9), max(north - south, 1e-9)
        pick = min if fit else max
        self.scale = pick((x2 - x1) / span_x, (y2 - y1) / span_y)
        self.cx, self.cy = (x1 + x2) / 2, (y1 + y2) / 2
        self.mid_lon, self.mid_lat = (west + east) / 2, (south + north) / 2

    def xy(self, lat: float, lon: float) -> tuple[float, float]:
        return (self.cx + (lon - self.mid_lon) * self.squeeze * self.scale,
                self.cy - (lat - self.mid_lat) * self.scale)


def bounds_of(lines: list[list[list[float]]]) -> tuple[float, float, float, float] | None:
    """Round the lines' points (or the corners of each run's bounds), with a margin."""
    points = [p for line in lines for p in line]
    if not points:
        return None
    lats, lons = [p[0] for p in points], [p[1] for p in points]
    pad_lat = max((max(lats) - min(lats)) * 0.08, 0.002)
    pad_lon = max((max(lons) - min(lons)) * 0.08, 0.002)
    return min(lats) - pad_lat, min(lons) - pad_lon, max(lats) + pad_lat, max(lons) + pad_lon


def town_layer(size: tuple[int, int], shapes: dict[str, list], frame: Frame,
               strength: float = 1.0, thick: int = 1) -> Image.Image:
    """The town's shapes on their own, on transparent: parks, water, then the streets by size.
    `thick` widens the lines for a picture drawn at more than one pixel per point."""

    def lines(kind: str, width: int, value: int) -> Image.Image:
        mask = Image.new("L", size, 0)
        draw = ImageDraw.Draw(mask)
        for line in shapes.get(kind) or []:
            draw.line([frame.xy(*p) for p in line], fill=value, width=width * thick,
                      joint="curve")
        return mask

    def areas(kind: str) -> Image.Image:
        mask = Image.new("L", size, 0)
        draw = ImageDraw.Draw(mask)
        for line in shapes.get(kind) or []:
            if len(line) >= 3 and line[0] == line[-1]:
                draw.polygon([frame.xy(*p) for p in line], fill=255)
        return mask

    layer = Image.new("RGBA", size, (0, 0, 0, 0))

    def lay(mask: Image.Image, colour: Colour, opacity: float) -> None:
        nonlocal layer
        top = Image.new("RGBA", size, (*colour, 255))
        top.putalpha(mask.point(lambda v: round(v * opacity)))
        layer = Image.alpha_composite(layer, top)

    lay(paint.soften(areas("park"), thick), (16, 24, 22), 0.9 * strength)
    water = ImageChops.lighter(areas("water"), lines("water", 6, 255))
    lay(paint.soften(water, thick), (10, 16, 34), strength)
    lay(paint.soften(lines("water", 2, 120), thick), (60, 90, 150), 0.5 * strength)
    for kind, width, value, colour in (("path", 1, 70, (120, 122, 140)),
                                       ("minor", 1, 120, (150, 152, 170)),
                                       ("major", 2, 160, (180, 180, 200))):
        lay(lines(kind, width, value), colour, 0.6 * strength)
    return layer


def town(base: Image.Image, shapes: dict[str, list], frame: Frame,
         strength: float = 1.0) -> Image.Image:
    """The town's shapes under the runs."""
    layer = town_layer(base.size, shapes, frame, strength)
    return Image.alpha_composite(base.convert("RGBA"), layer).convert("RGB")


def heat(size: tuple[int, int], routes: list[list[list[float]]], frame: Frame) -> Image.Image:
    """Every route as a little light that adds up where they overlap."""
    total = Image.new("L", size, 0)
    for route in routes:
        once = Image.new("L", size, 0)
        ImageDraw.Draw(once).line([frame.xy(*p) for p in route], fill=70, width=3, joint="curve")
        total = ImageChops.add(total, once)
    return total


def glow_by(base: Image.Image, total: Image.Image) -> Image.Image:
    """The heat in colour: ember where run once, amber, white-hot where run most."""
    soft = paint.soften(total, 3)
    base = paint.tint(base, soft.point(lambda v: min(255, v * 2)), EMBER, 0.55)
    base = paint.tint(base, total.point(lambda v: min(255, v * 2)), AMBER)
    return paint.tint(base, total.point(lambda v: max(0, v - 140) * 2), WHITE_HOT)


def inputs(screen: dict[str, Any], local: datetime) -> dict[str, Any] | None:
    """The year's runs by their count and newest (a list of ids would not fit a panel's answer),
    today's run, and when the streets were fetched: a new picture when any of them changes."""
    if not screen.get("present"):
        return None
    return {"since": screen["since"], "count": screen["count"], "newest": screen["newest"],
            "elsewhere": screen.get("elsewhere", 0), "today": screen.get("today_run"),
            "streets": screen.get("streets_at")}


def year_lines(store: Any, since: str) -> tuple[dict[str, Any], tuple | None]:
    """The home area's runs from `since` on (app/sources/streets.py, at_home) and their bounds:
    a run in another town would squeeze home's map to a corner."""
    home = streets.at_home(store, since)
    corners = [[[r["box"][0], r["box"][1]], [r["box"][2], r["box"][3]]] for r in home["runs"]]
    return home, bounds_of(corners)


def picture(store: Any, since: str, today: str | None, size: tuple[int, int],
            box: tuple[int, int, int, int]) -> Image.Image:
    home, bounds = year_lines(store, since)
    year = runs.routes(store, since, ids={r["id"] for r in home["runs"]})
    lines = [r["route"] for r in year]
    base = Image.new("RGB", size, (5, 5, 10))
    base = paint.tint(base, paint.vertical(size[1], [(0, (255,) * 3), (1, (0,) * 3)],
                                           width=size[0]).convert("L"), (12, 11, 22), 0.6)
    if bounds is None:
        return base
    frame = Frame(bounds, box)
    if home["streets"]:
        base = town(base, streets.shapes_of(store, home["streets"]["id"]), frame)
    base = glow_by(base, heat(size, lines, frame))
    today_route = next((r["route"] for r in year if r["id"] == today), None)
    if today_route:
        mask = Image.new("L", size, 0)
        ImageDraw.Draw(mask).line([frame.xy(*p) for p in today_route], fill=255, width=3,
                                  joint="curve")
        base = paint.tint(base, paint.soften(mask, 6), WHITE_HOT, 0.45)
        base = paint.tint(base, mask, WHITE_HOT)
    return base


def paint_streets(data: dict[str, Any], store: Any) -> Image.Image:
    base = picture(store, data["since"], data.get("today"), (SIZE, SIZE), MAP_BOX)
    top = paint.vertical(SIZE, [(0, (235,) * 3), (0.2, (120,) * 3), (0.3, (0,) * 3),
                                (1, (0,) * 3)]).convert("L")
    return paint.grain(paint.tint(base, top, (4, 4, 8)), 67, 3)


# The Running page's Last run card draws its route in this box (web/src/components/running/
# RouteArt.tsx: width, height and pad), fitted as `project` does; its streets match it.
ROUTE_ART = (640, 380, 40)
ROUTE_ART_SCALE = 2


def route_streets(route: list[list[Any]], shapes: dict[str, list]) -> bytes:
    """A run's area under the Last run card's route: the streets alone on transparent (WebP),
    placed exactly where the card draws the route, twice as sharp."""
    width, height, pad = ROUTE_ART
    s = ROUTE_ART_SCALE
    lats, lons = [p[0] for p in route], [p[1] for p in route]
    frame = Frame((min(lats), min(lons), max(lats), max(lons)),
                  (pad * s, pad * s, (width - pad) * s, (height - pad) * s), fit=True)
    out = io.BytesIO()
    town_layer((width * s, height * s), shapes, frame, thick=s).save(out, "WEBP", quality=82)
    return out.getvalue()


def web_jpeg(store: Any, since: str) -> bytes:
    """The hub's Running page card: the same picture, wider."""
    out = io.BytesIO()
    wide = picture(store, since, None, (1200, 720), (0, 0, 1200, 720))
    wide.save(out, "JPEG", quality=86)
    return out.getvalue()
