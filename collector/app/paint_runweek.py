"""B, the week against the plan (plan.md M28, step 4): a column per day, Runna's plan as a glass
outline, the distance run poured in as warm light with a glow, and the day's run in miniature
above it; today's column lit from below. The panel lays the words on top (app/desk_running.py,
whose columns these are)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from PIL import Image, ImageDraw

from . import paint
from .desk_running import WEEK_BOTTOM, WEEK_LEFT, WEEK_TOP, WEEK_WIDTH, project
from .paint import SIZE, SS
from .sources import runs

COLUMN_WIDTH = 46
MINI = 58  # the run in miniature above its column


def inputs(screen: dict[str, Any], local: datetime) -> dict[str, Any] | None:
    return {"week": screen["week"]} if screen.get("present") else None


def paint_runweek(data: dict[str, Any], store: Any) -> Image.Image:
    base = paint.vertical(SIZE, [(0, (8, 8, 14)), (0.6, (14, 11, 22)), (1, (6, 5, 10))])
    week = data["week"]
    top = max([1000.0] + [max(d["planned_m"], d["done_m"]) for d in week])
    span = WEEK_BOTTOM - WEEK_TOP - MINI - 16
    column = WEEK_WIDTH / 7
    layer, draw = paint.shapes()
    for i, d in enumerate(week):
        cx = WEEK_LEFT + column * (i + 0.5)
        x1, x2 = cx - COLUMN_WIDTH / 2, cx + COLUMN_WIDTH / 2
        if d.get("today"):
            paint.glow(base, cx, WEEK_BOTTOM, 120, (143, 128, 255), 0.22)
        if d["planned_m"]:
            h = d["planned_m"] / top * span
            draw.rounded_rectangle((x1 * SS, (WEEK_BOTTOM - h) * SS, x2 * SS, WEEK_BOTTOM * SS),
                                   radius=12 * SS, fill=(255, 255, 255, 10),
                                   outline=(255, 255, 255, 60), width=2 * SS)
        else:
            draw.rounded_rectangle(((cx - 10) * SS, (WEEK_BOTTOM - 5) * SS, (cx + 10) * SS,
                                    WEEK_BOTTOM * SS), radius=3 * SS, fill=(255, 255, 255, 30))
    base = paint.lay(base, layer)
    for i, d in enumerate(week):
        if not d["done_m"]:
            continue
        cx = WEEK_LEFT + column * (i + 0.5)
        h = d["done_m"] / top * span
        x1, x2, y1 = cx - COLUMN_WIDTH / 2 + 4, cx + COLUMN_WIDTH / 2 - 4, WEEK_BOTTOM - h
        paint.glow(base, cx, WEEK_BOTTOM - h / 2, round(max(60, h * 0.8)), (242, 166, 90), 0.3)
        fill = paint.vertical(SIZE, [(0, (255, 214, 160)), (y1 / SIZE, (255, 201, 143)),
                                     (WEEK_BOTTOM / SIZE, (200, 105, 46)), (1, (200, 105, 46))])
        mask = Image.new("L", (SIZE * SS, SIZE * SS), 0)
        ImageDraw.Draw(mask).rounded_rectangle((x1 * SS, y1 * SS, x2 * SS, WEEK_BOTTOM * SS),
                                               radius=10 * SS, fill=255)
        base = paint.tint(base, mask.resize((SIZE, SIZE), Image.Resampling.LANCZOS), fill)
        for run_id in d.get("runs") or []:
            run = runs.one(store, run_id, 40)
            if run and len(run["route"]) >= 2:
                box = (cx - MINI / 2, y1 - MINI - 10, cx + MINI / 2, y1 - 10)
                xy = project(run["route"], tuple(round(v) for v in box))
                line = Image.new("L", (SIZE, SIZE), 0)
                ImageDraw.Draw(line).line(xy, fill=255, width=2, joint="curve")
                base = paint.tint(base, paint.soften(line, 3), (242, 166, 90), 0.6)
                base = paint.tint(base, line, (255, 230, 200))
    return paint.grain(base, 59, 3)
