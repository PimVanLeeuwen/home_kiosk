"""The House panel's Code screen (plan.md M20, as chosen on 2026-10-21): your GitHub
contributions over 16 weeks as a grid, Monday first, and each week as a bar under
its column, with the week so far, the streak and the busiest weekday. The numbers
come from the Repos data's contribution calendar (`github.contributions`).
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any
from zoneinfo import ZoneInfo

from . import paint_code
from .store import Store

WEEKDAYS = ["Mondays", "Tuesdays", "Wednesdays", "Thursdays", "Fridays", "Saturdays", "Sundays"]


def _months(days: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """A month's name over the first week that starts in it (and over the first week)."""
    out, seen = [], set()
    for week in range(0, len(days), 7):
        first = date.fromisoformat(days[week]["day"])
        if week == 0 or first.month not in seen:
            seen.add(first.month)
            out.append({"week": week // 7, "name": first.strftime("%b")})
    return out


def _streak(counts: list[int]) -> int:
    """Days in a row with contributions, up to today (or yesterday, early in the day)."""
    if counts and counts[-1] == 0:
        counts = counts[:-1]
    streak = 0
    for count in reversed(counts):
        if count == 0:
            break
        streak += 1
    return streak


def code_screen(store: Store, zone: ZoneInfo, now: datetime) -> dict[str, Any]:
    activity = (store.get_cache("repos") or {}).get("activity") or {}
    days = activity.get("days") or []
    if not days:
        return {"kind": "code", "stale": False, "present": False}
    counts = [d["count"] for d in days]
    levels = [min(4, max(0, int(d.get("level", 0)))) for d in days]
    weeks = [sum(counts[i:i + 7]) for i in range(0, len(counts), 7)]
    top = max(weeks) or 1
    by_weekday = [sum(counts[i] for i in range(w, len(counts), 7)) for w in range(7)]
    streak = _streak(counts)
    return {
        "kind": "code", "stale": bool((store.get_cache("repos") or {}).get("stale")),
        "present": True,
        "title": "CODE · 16 WEEKS",
        "right": f"{activity.get('total', sum(counts))} CONTRIBUTIONS",
        "levels": levels,  # today last
        # The top of today's block in the painted city (plan.md M27): the panel's glow there.
        "city_today": list(paint_code.today_point(levels)),
        "months": _months(days),
        "weeks": [round(w / top * 1000) for w in weeks],
        "this_week": f"this week {weeks[-1]}",
        "streak": f"{streak}-day streak" if streak > 1 else "",
        "busiest": f"busiest on {WEEKDAYS[by_weekday.index(max(by_weekday))]}"
        if max(by_weekday) else "",
    }
