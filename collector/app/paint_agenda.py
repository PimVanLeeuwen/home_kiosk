"""The Calendar screen's background (plan.md M27, the lifted Calendar): the event that
is on, or next, lights the screen in its calendar's colour from behind its ring; the
event after it glows faintly from the other side; the violet corner and grain as on
every panel screen. The panel draws the ring, the words and the day's ribbon on top.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from PIL import Image

from . import paint
from .paint import SIZE, hex_colour

VIOLET = (124, 108, 242)


def inputs(screen: dict[str, Any], local: datetime) -> dict[str, Any] | None:
    """The colours of the event on now (or next) and the one after: these change only
    when an event starts or ends."""
    if not screen.get("present"):
        return None
    now = local.timestamp()
    ahead = [e for e in screen.get("events") or [] if e["end_at"] > now]
    if not ahead:
        return {"focus": None, "after": None, "on": False}
    focus = ahead[0]
    return {"focus": focus["color"], "after": ahead[1]["color"] if len(ahead) > 1 else None,
            "on": focus["start_at"] <= now}


def paint_agenda(data: dict[str, Any], store: Any = None) -> Image.Image:
    base = Image.new("RGB", (SIZE, SIZE), (0, 0, 0))
    paint.glow(base, SIZE - 60, -40, 420, VIOLET, 0.2, power=2.4)
    if data["focus"]:
        colour = hex_colour(data["focus"])
        # Brighter while it is on than while it is still to come.
        paint.glow(base, 130, 190, 560, colour, 0.3 if data["on"] else 0.18, power=2.2)
    if data["after"]:
        paint.glow(base, SIZE + 40, 640, 420, hex_colour(data["after"]), 0.1, power=2.2)
    return paint.grain(base, 7, 3)
