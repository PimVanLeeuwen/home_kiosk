"""The Now panel's calendar screen (plan.md M20): the hub's Today card
(web TodayCard, lib/today.ts) as ready-to-draw values, and since 2026-10-23
tomorrow's first events once today has nothing left. Shown on a day with
events (or with events tomorrow); the event under way or the next one is chosen on the panel, which
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


MAX_TOMORROW = 3
MAX_TOMORROW_ALL_DAY = 2


def _tomorrow(today: dict[str, Any], local: datetime, zone: ZoneInfo) -> dict[str, Any] | None:
    """Tomorrow's first events, when the hub read them for tomorrow's date."""
    later = today.get("tomorrow") or {}
    if later.get("date") != (local.date() + timedelta(days=1)).isoformat():
        return None
    events, all_day = later.get("events") or [], later.get("all_day") or []
    if not events and not all_day:
        return None
    day = datetime.fromisoformat(later["date"])
    count = len(events) + len(all_day)
    return {
        "title": f"Tomorrow · {day.strftime('%a %-d %b')}",
        "count": f"{count} event{'s' if count != 1 else ''}",
        "events": [{"title": latin1(e["title"]), "calendar": latin1(e["calendar"]),
                    "color": e["color"],
                    "start": datetime.fromisoformat(e["start"]).astimezone(zone).strftime("%H:%M"),
                    "end": datetime.fromisoformat(e["end"]).astimezone(zone).strftime("%H:%M")
                    if e.get("end") else ""}
                   for e in events[:MAX_TOMORROW]],
        "all_day": [{"title": latin1(e["title"]), "color": e["color"]}
                    for e in all_day[:MAX_TOMORROW_ALL_DAY]],
    }


def agenda_screen(store: Store, zone: ZoneInfo, now: datetime) -> dict[str, Any]:
    today = store.get_cache(agenda.CACHE_KEY)
    local = now.astimezone(zone)
    if not today or today.get("date") != local.date().isoformat():
        return {"kind": "agenda", "stale": False, "present": False}
    # Tomorrow shows once today has nothing left (all-day events do not count, or a
    # birthday would hold it all day), and on a day without events (decided 2026-10-23).
    left = [e for e in today.get("events") or []
            if datetime.fromisoformat(e.get("end") or e["start"]) > now]
    later = None if left else _tomorrow(today, local, zone)
    if not (today.get("events") or today.get("all_day")):
        if later is None:
            return {"kind": "agenda", "stale": False, "present": False}
        return {"kind": "agenda", "stale": bool(today.get("stale")), "present": True,
                "mode": "tomorrow", "today_line": "Nothing today",
                "title": later["title"], "count": later["count"], "events": [], "all_day": [],
                "tomorrow": later}

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
    answer = {
        "kind": "agenda", "stale": bool(today.get("stale")), "present": True,
        "mode": "today",
        "title": f"Today · {local.strftime('%a %-d %b')}",
        "count": f"{count} event{'s' if count != 1 else ''}",
        "events": events,
        "all_day": [{"title": latin1(e["title"]), "color": e["color"]}
                    for e in (today.get("all_day") or [])[:MAX_ALL_DAY]],
    }
    if later is not None:  # today is done: tomorrow below "Nothing more today"
        answer |= {"mode": "tomorrow", "today_line": "Nothing more today", "tomorrow": later}
    return answer
