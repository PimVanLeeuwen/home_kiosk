"""The Now panel's Todos screen (plan.md M37): the open todos in the hub's order, four a
page, turning like the Door panel's reminders. Read-only: ticking off stays in the hub.

In the rotation only while any is open. Titles and the due word only (no notes), so the
answer stays small; text goes through `latin1`, as the panel's fonts hold Latin-1 only.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any
from zoneinfo import ZoneInfo

from . import todos
from .panel_text import latin1
from .store import Store

MAX_TODOS = 12  # the panel turns through them, four a page


def due_word(due: date | None, day: date) -> str:
    """"3 days late", "Yesterday", "Today", "Tomorrow", "Sun 22 Nov"; "" without a date."""
    if due is None:
        return ""
    days = (due - day).days
    if days == 0:
        return "Today"
    if days == 1:
        return "Tomorrow"
    if days == -1:
        return "Yesterday"
    if days < 0:
        return f"{-days} days late"
    return f"{due:%a} {due.day} {due:%b}"


def todos_screen(store: Store, zone: ZoneInfo, now: datetime) -> dict[str, Any]:
    todos.ensure_tables(store)
    day = now.astimezone(zone).date()
    listed = todos.all_todos(store)
    if not listed:
        return {"kind": "todos", "stale": False, "present": False}
    overdue = sum(todos.state(t, day) == "overdue" for t in listed)
    title = f"TODOS · {len(listed)} OPEN" + (f" · {overdue} LATE" if overdue else "")
    return {
        "kind": "todos", "stale": False, "present": True,
        "title": title,
        "todos": [{"title": latin1(t.title), "due": due_word(t.due, day),
                   "state": todos.state(t, day) or "", "high": t.high}
                  for t in listed[:MAX_TODOS]],
        "more": max(0, len(listed) - MAX_TODOS),
    }
