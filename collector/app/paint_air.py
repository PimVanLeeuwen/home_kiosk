"""The Air screen's background (plan.md M27, the lifted Air): the room's air as light,
a glow round the CO2 ring in the colour of its word (fresh green, stuffy amber, red when
a window should open), and grain. The panel draws the ring, the words, the curve and a
few motes drifting through the air on top.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from PIL import Image

from . import paint
from .paint import SIZE, hex_colour

RING = (540, 262)  # the ring's centre (panels/firmware/main/screen_air.c)


def inputs(screen: dict[str, Any], local: datetime) -> dict[str, Any] | None:
    """Only the colour of the CO2 word: the glow changes when the air does."""
    if not screen.get("present") or not screen.get("colour"):
        return None
    return {"colour": screen["colour"]}


def paint_air(data: dict[str, Any], store: Any = None) -> Image.Image:
    colour = hex_colour(data["colour"])
    base = Image.new("RGB", (SIZE, SIZE), (0, 0, 0))
    paint.glow(base, *RING, 320, colour, 0.36, power=2.0)
    # The same air low over the 8-hour curve, faintly.
    paint.glow(base, SIZE // 2, 600, 420, colour, 0.07, power=2.0)
    return paint.grain(base, 5, 3)
