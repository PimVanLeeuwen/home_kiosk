"""Today's move of the whole portfolio, the same everywhere in the hub.

The sum of the holdings' moves (each from its last close against the one
before), not Ghostfolio's own day figure: before the US open that one covers a
barely started session while the holdings show the last one, so the two would
disagree on one screen. stock-bot summed the holdings the same way.
"""

from __future__ import annotations

from typing import Any


def day_move(portfolio: dict[str, Any]) -> tuple[float, float]:
    """(euros, percent). Falls back to Ghostfolio's figure for payloads from
    before the holdings carried their move in euros."""
    holdings = portfolio.get("holdings") or []
    if not holdings or any(h.get("day_abs") is None for h in holdings):
        change = portfolio.get("change") or {}
        return change.get("day_abs") or 0.0, change.get("day_pct") or 0.0
    move = sum(h["day_abs"] for h in holdings)
    before = portfolio["total_value"] - move
    return round(move, 2), round(move / before * 100, 2) if before else 0.0
