"""The House panel's Money screen (plan.md M20, the design of 2026-10-10, adapted
2026-10-23): the portfolio over a week, a month, a year or all of it, switched on the
panel, with today's change in its pill. Percentages only (decided 2026-10-23: the desk
is visible to visitors): no euro amounts leave the hub for the panel, and the chart's
points are scaled to 0..1000.

As on the hub's Portfolio page, a period's gain leaves deposits out: the line is the
value minus what was put in, and its percentage is that gain over what was there at the
start plus what was added. There is no intraday history, so no day chart.
"""

from __future__ import annotations

from datetime import date
from typing import Any
from zoneinfo import ZoneInfo

from .sources import ghostfolio
from .store import Store

MAX_POINTS = 60
# The panel's switch: its label, where the points come from, how many days back.
PERIODS = (("1W", "this week", "month", 7), ("1M", "this month", "month", None),
           ("1Y", "this year", "year", None), ("All", "all time", "max", None))


def pct(value: float) -> str:
    """"+4.2%", "-0.7%", "0.0%"."""
    if round(value, 1) == 0:
        return "0.0%"
    return f"{'+' if value > 0 else '-'}{abs(value):.1f}%"


def _thin(points: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """At most MAX_POINTS, evenly spread, always with the first and the last."""
    if len(points) <= MAX_POINTS:
        return points
    step = (len(points) - 1) / (MAX_POINTS - 1)
    return [points[round(i * step)] for i in range(MAX_POINTS)]


def _short(day: str) -> str:
    d = date.fromisoformat(day[:10])
    return f"{d.day} {d.strftime('%b')}"


def period(points: list[dict[str, Any]], key: str, label: str) -> dict[str, Any] | None:
    """One switch position: its gain, the gain line scaled to 0..1000 and its best point."""
    points = [p for p in points if p.get("v") is not None and p.get("invested") is not None]
    if len(points) < 2:
        return None
    first, last = points[0], points[-1]
    gains = [p["v"] - p["invested"] - (first["v"] - first["invested"]) for p in points]
    base = first["v"] + max(0.0, last["invested"] - first["invested"])
    if base <= 0:
        return None
    thinned = _thin(list(zip(points, gains, strict=True)))
    line = [g for _, g in thinned]
    low, high = min(line), max(line)
    span = high - low or 1.0
    best = line.index(high)
    return {
        "key": key, "label": label,
        "change": pct(100 * gains[-1] / base), "up": gains[-1] >= 0,
        "points": [round((g - low) / span * 1000) for g in line],
        "high_at": best, "high": pct(100 * high / base),
        "from": _short(first["d"]), "to": "Today",
    }


def money_screen(store: Store, zone: ZoneInfo, now: Any) -> dict[str, Any]:
    charts = store.get_cache(ghostfolio.CHARTS_KEY) or {}
    ranges = charts.get("ranges") or {}
    periods = []
    for key, label, source, days in PERIODS:
        points = ranges.get(source) or []
        found = period(points[-(days + 1):] if days else points, key, label)
        if found:
            periods.append(found)
    if not periods:
        return {"kind": "money", "stale": False, "present": False}
    today = ((store.get_cache("portfolio") or {}).get("change") or {}).get("day_pct")
    return {
        "kind": "money",
        "stale": bool(charts.get("stale")),
        "present": True,
        "title": "PORTFOLIO",
        "today": f"TODAY {pct(today)}" if today is not None else "",
        "today_up": (today or 0) >= 0,
        "periods": periods,
    }
