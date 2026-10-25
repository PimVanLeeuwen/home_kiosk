"""The Now panel's Briefing screen (plan.md M26, step 3b): the morning digest's
line and four facts, until 09:00 on the day it was written (app/briefing.py).
Text goes through `latin1`, as the panel's fonts hold Latin-1 only.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from .briefing import CACHE_KEY
from .panel_text import latin1
from .store import Store


def briefing_screen(store: Store, zone: ZoneInfo, now: datetime) -> dict[str, Any]:
    b = store.get_cache(CACHE_KEY) or {}
    local = now.astimezone(zone)
    shown = (b.get("date") == local.date().isoformat() and b.get("until")
             and now < datetime.fromisoformat(b["until"]))
    if not shown:
        return {"kind": "briefing", "stale": False, "present": False}
    made = datetime.fromisoformat(b["as_of"]).astimezone(zone)
    return {
        "kind": "briefing", "stale": bool(b.get("stale")), "present": True,
        "title": f"BRIEFING · {local:%A}".upper(),
        "line": latin1(b.get("line") or ""),
        "facts": [latin1(f) for f in b.get("facts") or []][:4],
        "as_of": f"written by Claude at {made:%H:%M}",
    }
