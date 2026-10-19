"""The Now panel's calendar screen (plan.md M20): the hub's Today card
(web TodayCard, lib/today.ts) as ready-to-draw values. Shown on a day with
events; the event under way or the next one is chosen on the panel, which
counts the minutes down on its own clock, so each event carries its start and
end as seconds since 1970 besides its place on the 07:00 to 23:00 ribbon.

Event titles are personal: served to the hub and the panels, never logged.
"""

from __future__ import annotations

from datetime import datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from .panel_text import latin1
from .sources import agenda
from .store import Store

MAX_EVENTS = 12
MAX_ALL_DAY = 3


def _minute(at: datetime, day_start: datetime) -> int:
    """Minutes since local midnight, clamped to today (an event from yesterday starts at 0)."""
    return max(0, min(24 * 60, round((at - day_start).total_seconds() / 60)))


def agenda_screen(store: Store, zone: ZoneInfo, now: datetime) -> dict[str, Any]:
    today = store.get_cache(agenda.CACHE_KEY)
    local = now.astimezone(zone)
    if (not today or today.get("date") != local.date().isoformat()
            or not (today.get("events") or today.get("all_day"))):
        return {"kind": "agenda", "stale": False, "present": False}

    day_start = datetime.combine(local.date(), time(0), zone)
    events = []
    for e in (today.get("events") or [])[:MAX_EVENTS]:
        start = datetime.fromisoformat(e["start"])
        end = datetime.fromisoformat(e["end"]) if e.get("end") else start + timedelta(minutes=15)
        events.append({
            "title": latin1(e["title"]), "calendar": latin1(e["calendar"]), "color": e["color"],
            "start_at": round(start.timestamp()), "end_at": round(end.timestamp()),
            "start_minute": _minute(start, day_start), "end_minute": _minute(end, day_start),
            # From an earlier day: "" (the ribbon starts it at 00:00).
            "start": start.astimezone(zone).strftime("%H:%M") if start >= day_start else "",
            "end": end.astimezone(zone).strftime("%H:%M"),
        })
    count = len(today.get("events") or []) + len(today.get("all_day") or [])
    return {
        "kind": "agenda", "stale": bool(today.get("stale")), "present": True,
        "title": f"Today · {local.strftime('%a %-d %b')}",
        "count": f"{count} event{'s' if count != 1 else ''}",
        "events": events,
        "all_day": [{"title": latin1(e["title"]), "color": e["color"]}
                    for e in (today.get("all_day") or [])[:MAX_ALL_DAY]],
    }
