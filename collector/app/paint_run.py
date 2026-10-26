"""A, the last run (plan.md M28, step 4): the route as light on the dark, every stretch in the
colour of its pace against the run's own range (cool blue easy, amber, white at its fastest),
over a soft glow of the whole line; a ring where it started, a lit point where it finished.
The panel lays the numbers on top and runs a light along the route (screen_piece.c), on the
same box (app/desk_running.py). The streets under it come with step 5."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from PIL import Image, ImageDraw

from . import paint
from .desk_running import ROUTE_BOX, project
from .paint import SIZE, SS, Colour, mix
from .sources import runs

COOL: Colour = (94, 140, 255)
WARM: Colour = (255, 168, 92)
HOT: Colour = (255, 244, 222)


def inputs(screen: dict[str, Any], local: datetime) -> dict[str, Any] | None:
    return {"id": screen["id"]} if screen.get("present") else None


def pace_colour(pace: float | None, slowest: float, fastest: float) -> Colour:
    if pace is None or slowest <= fastest:
        return WARM
    t = max(0.0, min(1.0, (slowest - pace) / (slowest - fastest)))
    return mix(COOL, WARM, t / 0.7) if t < 0.7 else mix(WARM, HOT, (t - 0.7) / 0.3)


def pace_range(points: list[list[Any]]) -> tuple[float, float]:
    paces = sorted(p[2] for p in points if p[2] is not None and 120 < p[2] < 1200)
    if not paces:
        return 360.0, 300.0
    return paces[int(len(paces) * 0.95) if len(paces) > 1 else 0], paces[int(len(paces) * 0.05)]


def paint_run(data: dict[str, Any], store: Any) -> Image.Image | None:
    run = runs.one(store, data["id"], 400)
    if run is None:
        return None
    base = paint.vertical(SIZE, [(0, (6, 6, 12)), (0.45, (10, 9, 20)), (1, (4, 4, 8))])
    paint.glow(base, 360, 520, 420, (60, 50, 110), 0.25, power=1.8)
    route = run["route"]
    if len(route) >= 2:
        xy = project(route, ROUTE_BOX)
        slowest, fastest = pace_range(route)
        glow = Image.new("L", (SIZE, SIZE), 0)
        ImageDraw.Draw(glow).line(xy, fill=255, width=14, joint="curve")
        base = paint.tint(base, paint.soften(glow, 14), (242, 166, 90), 0.38)
        layer, draw = paint.shapes()
        for (a, b), p in zip(zip(xy, xy[1:], strict=False), route[1:], strict=False):
            draw.line((a[0] * SS, a[1] * SS, b[0] * SS, b[1] * SS),
                      fill=(*pace_colour(p[2], slowest, fastest), 255), width=5 * SS)
            paint.disc(draw, b[0], b[1], 2.4, (*pace_colour(p[2], slowest, fastest), 255))
        (sx, sy), (ex, ey) = xy[0], xy[-1]
        draw.ellipse(((sx - 8) * SS, (sy - 8) * SS, (sx + 8) * SS, (sy + 8) * SS),
                     outline=(255, 255, 255, 255), width=3 * SS)
        base = paint.lay(base, layer)
        paint.glow(base, ex, ey, 40, HOT, 0.5)
        layer, draw = paint.shapes()
        paint.disc(draw, ex, ey, 9, (*HOT, 255))
        base = paint.lay(base, layer)
    # Darker behind the numbers at the top.
    top = paint.vertical(SIZE, [(0, (190,) * 3), (0.42, (0,) * 3), (1, (0,) * 3)]).convert("L")
    base = paint.tint(base, top, (4, 4, 8))
    return paint.grain(base, 53, 3)
