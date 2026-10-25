"""The Headlines screen's background (plan.md M27, the lifted Headlines): the lead
story's picture edge to edge over the top of the screen, darkened at the top for its
badge, with a frosted glass panel where its title sits, fading into black for the two
stories below. The panel lays the badge, the title and the rows on top as text.

The geometry is the panel's when painted (panels/firmware/main/screen_headlines.c):
the picture down to 440, the glass from 254 to 432, 24 from either side.
"""

from __future__ import annotations

import io
from datetime import datetime
from typing import Any

from PIL import Image, ImageDraw, ImageOps

from . import paint
from .news import headlines
from .paint import SIZE, SS
from .store import Store

PICTURE_H = 440
GLASS = (24, 254, SIZE - 24, 432)  # room for a title of three lines
RADIUS = 22


def inputs(screen: dict[str, Any], local: datetime) -> dict[str, Any] | None:
    """The lead story, when it has a picture of its own; without one the panel keeps its
    plain card."""
    stories = screen.get("stories") or []
    if not screen.get("present") or not stories or not stories[0].get("picture"):
        return None
    return {"lead": stories[0]["id"]}


def paint_headlines(data: dict[str, Any], store: Store) -> Image.Image | None:
    stored = headlines.picture(store, data["lead"], "lead")
    if not stored:
        return None
    with Image.open(io.BytesIO(stored)) as raw:
        picture = ImageOps.fit(raw.convert("RGB"), (SIZE, PICTURE_H), Image.Resampling.LANCZOS)
    base = Image.new("RGB", (SIZE, SIZE), (0, 0, 0))
    base.paste(picture, (0, 0))

    # Darker at the top (the badge and the bookmark) and fading into black at the foot.
    shade = paint.vertical(SIZE, [(0, (150,) * 3), (0.17, (0,) * 3), (0.52, (0,) * 3),
                                  (0.62, (255,) * 3), (1, (255,) * 3)]).convert("L")
    base = paint.tint(base, shade, (0, 0, 0))

    # The glass: the picture behind it blurred, a little darker, with a fine light edge.
    x1, y1, x2, y2 = GLASS
    frosted = paint.soften(base.crop(GLASS), 16)
    frosted = Image.blend(frosted, Image.new("RGB", frosted.size, (14, 12, 22)), 0.38)
    mask = Image.new("L", ((x2 - x1) * SS, (y2 - y1) * SS), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, (x2 - x1) * SS - 1, (y2 - y1) * SS - 1),
                                           radius=RADIUS * SS, fill=255)
    mask = mask.resize((x2 - x1, y2 - y1), Image.Resampling.LANCZOS)
    shadow = paint.soften(mask, 10).point(lambda v: v * 90 // 255)
    base.paste(Image.new("RGB", mask.size, (0, 0, 0)), (x1, y1 + 8), shadow)
    base.paste(frosted, (x1, y1), mask)
    layer, draw = paint.shapes()
    draw.rounded_rectangle((x1 * SS, y1 * SS, x2 * SS, y2 * SS), radius=RADIUS * SS,
                           outline=(255, 255, 255, 46), width=SS)
    base = paint.lay(base, layer)
    return paint.grain(base, 11, 2)
