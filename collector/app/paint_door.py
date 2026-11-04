"""The Door panel's background (plan.md M32): the violet corner behind the clock, warmer in
the morning and deeper at night; a cool blue light behind the rain while rain is coming; a
rose glow by the birthdays on someone's birthday. The panel draws the clock, the words and
the rain's bars on top.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from PIL import Image

from . import paint
from .paint import SIZE

VIOLET = (124, 108, 242)
DAWN = (226, 150, 110)
RAIN = (90, 150, 240)
ROSE = (230, 120, 170)


def _part(hour: int) -> str:
    if 6 <= hour < 10:
        return "morning"
    if 10 <= hour < 18:
        return "day"
    return "evening" if 18 <= hour < 23 else "night"


def inputs(screen: dict[str, Any], local: datetime) -> dict[str, Any] | None:
    """The part of the day, whether rain is coming and whether it is someone's birthday:
    these change a few times a day at most."""
    if not screen.get("present"):
        return None
    return {"part": _part(local.hour), "wet": bool(screen.get("wet")),
            "birthday": any(b.get("today") for b in screen.get("birthdays") or [])}


def paint_door(data: dict[str, Any], store: Any = None) -> Image.Image:
    base = Image.new("RGB", (SIZE, SIZE), (0, 0, 0))
    strength = {"morning": 0.3, "day": 0.26, "evening": 0.24, "night": 0.16}[data["part"]]
    paint.glow(base, 80, -30, 520, VIOLET, strength, power=2.3)
    if data["part"] == "morning":
        paint.glow(base, SIZE - 40, -60, 380, DAWN, 0.14, power=2.4)
    if data["wet"]:
        paint.glow(base, SIZE // 2, 240, 400, RAIN, 0.14, power=2.2)
    if data["birthday"]:
        paint.glow(base, SIZE - 60, 470, 340, ROSE, 0.16, power=2.2)
    return paint.grain(base, 11, 3)
