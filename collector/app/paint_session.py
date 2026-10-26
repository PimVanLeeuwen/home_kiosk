"""C, the next session (plan.md M28, step 4): Runna's workout as its shape, each block as wide as
it lasts and as tall as it is hard, glowing from blue for easy to amber and cream for the
fastest, mirrored in a glass floor. The panel lays the name, the facts and the steps on top
(app/desk_running.py, whose box this is)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from PIL import Image, ImageChops, ImageDraw

from . import paint
from .desk_running import BLOCKS_BOX
from .paint import SIZE, SS, Colour, mix

EASY_PACE = 360
EASY: Colour = (106, 127, 216)
WORK: Colour = (242, 166, 90)
FAST: Colour = (255, 217, 168)
REST: Colour = (58, 58, 74)


def inputs(screen: dict[str, Any], local: datetime) -> dict[str, Any] | None:
    return {"blocks": screen["blocks"]} if screen.get("present") else None


def seconds(block: dict[str, Any]) -> float:
    if block.get("seconds"):
        return float(block["seconds"])
    return (block.get("metres") or 0) / 1000 * (block.get("pace") or EASY_PACE)


def paint_session(data: dict[str, Any], store: Any = None) -> Image.Image:
    base = paint.vertical(SIZE, [(0, (8, 8, 14)), (0.55, (13, 11, 22)), (1, (5, 5, 9))])
    blocks = data["blocks"] or [{"kind": "easy", "metres": 5000, "seconds": None, "pace": None}]
    x1, y1, x2, floor = BLOCKS_BOX
    total = sum(seconds(b) for b in blocks) or 1
    paces = [b["pace"] for b in blocks if b["kind"] == "work" and b.get("pace")]
    fastest = min(paces + [EASY_PACE])
    gap, x = 4, float(x1)
    shapes = []
    for b in blocks:
        w = max(4.0, seconds(b) / total * (x2 - x1) - gap)
        if b["kind"] == "rest":
            effort, colour = 0.12, REST
        elif b["kind"] == "easy" or not b.get("pace"):
            effort, colour = 0.34, EASY
        else:
            effort = 0.45 + 0.55 * min(1, (EASY_PACE - b["pace"]) / max(1, EASY_PACE - fastest))
            colour = FAST if effort > 0.85 else WORK
        shapes.append((x, w, effort * (floor - y1), colour))
        x += w + gap
    for sx, w, h, colour in shapes:
        if colour is not REST:
            paint.glow(base, sx + w / 2, floor - h / 2, round(max(40, h * 0.7)), colour, 0.18)
    # Each block lit from above: lighter at its top, its own colour at the floor.
    for sx, w, h, colour in shapes:
        mask = Image.new("L", (SIZE * SS, SIZE * SS), 0)
        ImageDraw.Draw(mask).rounded_rectangle((sx * SS, (floor - h) * SS, (sx + w) * SS,
                                                floor * SS), radius=6 * SS, fill=255)
        light = paint.vertical(SIZE, [(0, mix(colour, (255, 255, 255), 0.4)),
                                      ((floor - h) / SIZE, mix(colour, (255, 255, 255), 0.4)),
                                      (floor / SIZE, mix(colour, (0, 0, 0), 0.25)),
                                      (1, colour)])
        base = paint.tint(base, mask.resize((SIZE, SIZE), Image.Resampling.LANCZOS), light)
    # The glass floor: each block mirrored, faint and fading.
    mirror = Image.new("L", (SIZE, SIZE), 0)
    md = ImageDraw.Draw(mirror)
    for sx, w, h, _ in shapes:
        md.rectangle((sx, floor + 4, sx + w, floor + 4 + min(46, h * 0.45)), fill=70)
    fade = paint.vertical(SIZE, [(0, (255,) * 3), (floor / SIZE, (255,) * 3),
                                 ((floor + 50) / SIZE, (0,) * 3), (1, (0,) * 3)]).convert("L")
    reflection = ImageChops.multiply(paint.soften(mirror, 2), fade)
    base = paint.tint(base, reflection, (200, 170, 140))
    line = Image.new("L", (SIZE, SIZE), 0)
    ImageDraw.Draw(line).line((x1, floor + 2, x2, floor + 2), fill=90, width=1)
    base = paint.tint(base, line, (255, 255, 255), 0.6)
    return paint.grain(base, 61, 3)
