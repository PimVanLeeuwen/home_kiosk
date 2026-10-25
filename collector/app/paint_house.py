"""The House panel's backgrounds (plan.md M27, the lifted House screens): each screen lit
by how things stand, in one light where its main thing sits (the gauge, the seal, the
chart, the hero alert): violet as the hub's own colour, green while all is well, amber
for something to look at, red for something wrong; the violet corner and grain as on
every panel screen. The panel draws everything else on top, its tiles as glass.

One painter for all of them: the screens differ only in where the light sits and what
colours it, so a picture changes when the state does, not with the numbers.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Any

from PIL import Image

from . import paint
from .paint import SIZE, hex_colour

VIOLET, GREEN, AMBER, RED, BLUE = "#8f80ff", "#3fb97f", "#e0a23b", "#e5646a", "#5aa9ff"
CORNER = (124, 108, 242)

Spot = tuple[int, int, int, float]  # x, y, radius, strength


def _nas(s: dict[str, Any]) -> str:
    used, limit = s.get("used_pct") or 0, s.get("limit_pct") or 90
    return RED if used >= limit else AMBER if s.get("warn") else VIOLET  # as its pill says


def _tone(tone: str | None) -> str:
    """A service's or an alert's state as a colour."""
    if tone in (None, "ok", "operational", "info"):
        return GREEN
    if tone in ("maintenance",):
        return BLUE
    if tone in ("error", "major", "outage", "major_outage", "down"):
        return RED
    return AMBER


def _backups(s: dict[str, Any]) -> str:
    return RED if not s.get("ok", True) else AMBER if s.get("warn") else GREEN


# Per screen: its colour from the screen, and where its light sits.
SCREENS: dict[str, tuple[Callable[[dict[str, Any]], str], Spot]] = {
    "nas": (_nas, (360, 180, 330, 0.34)),
    "code": (lambda s: VIOLET, (360, 500, 420, 0.26)),
    "sites": (lambda s: RED if s.get("down") else GREEN, (360, 380, 460, 0.2)),
    "services": (lambda s: _tone(s.get("tone")), (360, 330, 400, 0.28)),
    "tailnet": (lambda s: AMBER if s.get("warn") else VIOLET, (360, 300, 380, 0.3)),
    # Violet: the chart's own colour depends on the period chosen on the panel.
    "money": (lambda s: VIOLET, (360, 430, 440, 0.24)),
    "movers": (lambda s: GREEN if s.get("total_up", True) else RED, (360, 380, 480, 0.2)),
    "media": (lambda s: VIOLET if s.get("tone") in (None, "ok") else AMBER, (180, 200, 360, 0.26)),
    "backups": (_backups, (120, 150, 330, 0.34)),
    "alerts": (lambda s: _tone(s.get("tone")), (130, 180, 400, 0.32)),
    "pipelines": (lambda s: VIOLET, (360, 330, 400, 0.24)),
    "pipeline": (lambda s: s.get("colour") or VIOLET, (190, 300, 400, 0.28)),
}


def inputs_for(kind: str) -> Callable[[dict[str, Any], datetime], dict[str, Any] | None]:
    def inputs(screen: dict[str, Any], local: datetime) -> dict[str, Any] | None:
        if not screen.get("present"):
            return None
        colour, spot = SCREENS[kind]
        return {"colour": colour(screen), "spot": list(spot)}

    return inputs


def paint_house(data: dict[str, Any], store: Any = None) -> Image.Image:
    base = Image.new("RGB", (SIZE, SIZE), (0, 0, 0))
    paint.glow(base, SIZE - 60, -40, 420, CORNER, 0.2, power=2.4)
    x, y, radius, strength = data["spot"]
    paint.glow(base, x, y, radius, hex_colour(data["colour"]), strength, power=2.0)
    return paint.grain(base, 23, 3)
