"""The Laundry screen's background (plan.md M27, the lifted Laundry): a chrome rim round
each glass door, lit from the top left, and a soft light in the colour of where the
machine is (violet while it runs, green when it is done, amber paused, red on an error);
grain. The panel draws the ring, the door with its water, the words and the bubbles.

The layout is the panel's (panels/firmware/main/screen_laundry.c, arrange()): one machine
that is on, alone and large, when the other is not; else both side by side.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from PIL import Image, ImageChops, ImageDraw

from . import paint
from .paint import SIZE, SS, hex_colour

RUNNING = "#9c8ffb"


def _active(m: dict[str, Any]) -> bool:
    return m.get("state") not in (None, "idle")


def layout(machines: list[dict[str, Any]]) -> int:
    """The machine shown alone (0 or 1), or -1 for both side by side (as the panel)."""
    on = [_active(m) for m in machines] + [False, False]
    if on[0] and not on[1]:
        return 0
    if on[1] and not on[0]:
        return 1
    return -1


def doors(which: int, count: int) -> list[tuple[float, float, float, float]]:
    """(x, y, door radius, ring radius) for each porthole shown."""
    if which >= 0:
        return [(36 + 165, 120 + 165, 130, 165)]
    return [(36 + i * 324 + 162, 110 + 125, 95, 125) for i in range(count)]


def inputs(screen: dict[str, Any], local: datetime) -> dict[str, Any] | None:
    """The layout and each shown machine's colour: changes when a machine starts, ends
    or pauses, not with the minutes."""
    machines = screen.get("machines") or []
    if not screen.get("present") or not machines:
        return None
    which = layout(machines)
    shown = [machines[which]] if which >= 0 else machines
    return {"which": which, "count": len(machines),
            "colours": [m["colour"] if m["state"] != "running" else RUNNING for m in shown]}


def _rim(base: Image.Image, x: float, y: float, inner: float, outer: float) -> Image.Image:
    """Brushed metal between the door and the ring: bright at the top left, dark below."""
    mask = Image.new("L", (SIZE * SS, SIZE * SS), 0)
    draw = ImageDraw.Draw(mask)
    draw.ellipse(((x - outer) * SS, (y - outer) * SS, (x + outer) * SS, (y + outer) * SS), fill=255)
    draw.ellipse(((x - inner) * SS, (y - inner) * SS, (x + inner) * SS, (y + inner) * SS), fill=0)
    mask = mask.resize((SIZE, SIZE), Image.Resampling.LANCZOS)
    metal = Image.linear_gradient("L").rotate(45, expand=False).resize((SIZE, SIZE))
    metal = ImageChops.offset(metal, round(x - SIZE / 2), round(y - SIZE / 2))
    metal = metal.point(lambda v: 40 + v * 150 // 255)
    cool = [metal.point(lambda v: v * 92 // 100), metal.point(lambda v: v * 94 // 100), metal]
    steel = Image.merge("RGB", cool)
    return paint.tint(base, mask, steel)


def paint_laundry(data: dict[str, Any], store: Any = None) -> Image.Image:
    base = Image.new("RGB", (SIZE, SIZE), (0, 0, 0))
    spots = doors(data["which"], data["count"])
    for (x, y, _door, ring), colour in zip(spots, data["colours"], strict=False):
        paint.glow(base, x, y, round(ring * 2.2), hex_colour(colour), 0.22, power=2.0)
    for x, y, door, ring in spots:
        base = _rim(base, x, y, door - 2, ring - 12)
    return paint.grain(base, 19, 3)
