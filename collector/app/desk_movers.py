"""The House panel's Top movers screen (plan.md M20, the heat map as chosen again on
2026-10-22): the holdings as tiles sized by their share of the portfolio and tinted by
today's move, the ones under 2% together in one "others" tile, and the indices below.
The hub lays the tiles out (as the Portfolio page's MoversCard does), so the panel
only draws rectangles.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from .store import Store

# The heat map's box on the 720 px panel.
BOX_X, BOX_Y, BOX_W, BOX_H = 36, 96, 648, 540
MIN_WEIGHT = 2.0  # below this a holding goes into the "others" tile
MAX_TILES = 12


def squarify(weights: list[float], w: float, h: float) -> list[tuple[float, float, float, float]]:
    """A squarified treemap (Bruls, Huizing and van Wijk), as web/src/lib/treemap.ts:
    a rectangle per weight, largest first, as close to square as the weights allow."""
    total = sum(max(0.0, x) for x in weights)
    if not weights or total <= 0 or w <= 0 or h <= 0:
        return []
    scale = w * h / total
    rest = [max(0.0, x) * scale for x in weights]
    out: list[tuple[float, float, float, float]] = []
    x = y = 0.0

    def worst(row: list[float], side: float) -> float:
        s = sum(row)
        return max(side * side * max(row) / (s * s), (s * s) / (side * side * min(row) or 1))

    while rest:
        side = min(w, h)
        row = [rest[0]]
        best = worst(row, side)
        for area in rest[1:]:
            score = worst([*row, area], side)
            if score > best:
                break
            row.append(area)
            best = score
        s = sum(row)
        if w >= h:
            cw, cy = s / h, y
            for area in row:
                out.append((x, cy, cw, area / cw))
                cy += area / cw
            x, w = x + cw, w - cw
        else:
            ch, cx = s / w, x
            for area in row:
                out.append((cx, y, area / ch, ch))
                cx += area / ch
            y, h = y + ch, h - ch
        rest = rest[len(row):]
    return out


def _pct(value: float) -> str:
    """"+2.54%", "-0.27%": a plain hyphen, as the panel fonts stop at Latin-1."""
    return f"{'+' if value >= 0 else '-'}{abs(value):.2f}%"


def _ticker(symbol: str) -> str:
    """Without the exchange: "XDWT.L" is "XDWT"."""
    return symbol.split(".")[0] if "." in symbol else symbol


def _size(w: int, h: int) -> str:
    """What fits: "lg" ticker, change and name; "md" ticker and change; "sm" the ticker."""
    return "lg" if w >= 150 and h >= 150 else "md" if w >= 96 and h >= 64 else "sm"


def movers_screen(store: Store, zone: ZoneInfo, now: datetime) -> dict[str, Any]:
    data = store.get_cache("portfolio") or {}
    holdings = sorted((h for h in data.get("holdings") or [] if h.get("weight_pct", 0) > 0),
                      key=lambda h: h["weight_pct"], reverse=True)
    if not holdings:
        return {"kind": "movers", "stale": False, "present": False}
    big = [h for h in holdings if h["weight_pct"] >= MIN_WEIGHT][:MAX_TILES - 1]
    small = holdings[len(big):]
    cells = [{"ticker": _ticker(h["symbol"]), "name": h.get("name") or "",
              "weight": h["weight_pct"], "move": h.get("day_pct") or 0.0} for h in big]
    if small:
        weight = sum(h["weight_pct"] for h in small)
        # Their move together, weighted by their size.
        move = sum(h["weight_pct"] * (h.get("day_pct") or 0.0) for h in small) / weight
        ticker = f"{len(small)} others" if len(small) > 1 else _ticker(small[0]["symbol"])
        cells.append({"ticker": ticker, "name": "", "weight": weight, "move": move})
    tiles = []
    for cell, (x, y, w, h) in zip(cells, squarify([c["weight"] for c in cells], BOX_W, BOX_H),
                                  strict=True):
        left, top = round(BOX_X + x), round(BOX_Y + y)
        width, height = round(BOX_X + x + w) - left, round(BOX_Y + y + h) - top
        ticker = cell["ticker"]
        if ticker.endswith(" others") and width < 140:
            ticker = "+" + ticker.split()[0]  # "+3" where "3 others" does not fit
        tiles.append({"x": left, "y": top, "w": width, "h": height,
                      "size": _size(width, height), "ticker": ticker,
                      "name": cell["name"], "change": _pct(cell["move"]),
                      "move": round(cell["move"] * 100)})  # in hundredths of a percent
    day = (data.get("change") or {}).get("day_pct")
    indices = (store.get_cache("indices") or {}).get("indices") or []
    return {
        "kind": "movers",
        "stale": bool(data.get("stale")),
        "present": True,
        "title": "TOP MOVERS · TODAY",
        "total": f"portfolio {_pct(day)}" if day is not None else "",
        "total_up": day is None or day >= 0,
        "tiles": tiles,
        "indices": [{"label": i.get("label") or i.get("symbol") or "?",
                     "change": _pct(i["day_pct"]), "up": i["day_pct"] >= 0}
                    for i in indices[:3] if i.get("day_pct") is not None],
    }
