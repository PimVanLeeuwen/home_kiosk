"""Todos (plan.md M37): what the owner wants done, kept until it is, for the Todos page, a
card on Home, the Now panel, a daily ntfy message and Claude.

A todo has a title, and optionally a short note, a due date and a High flag. Ticking one off
removes it; the hub's Undo puts it back as it was (`restore`, same id and age), so there is
no Done list and no history. Once a day, at the time set in Settings, Todos (08:00 until
changed), one ntfy message lists what is open (`send_daily`); none when nothing is.

Titles and notes are personal data: served to the hub, the panel and the MCP tools, never
logged.
"""

from __future__ import annotations

import weakref
from datetime import UTC, date, datetime, time, timedelta
from typing import Annotated, Any

from pydantic import BaseModel, StringConstraints, field_validator

from . import config
from .alerts import core
from .store import Store

TABLES = """
CREATE TABLE IF NOT EXISTS todo (
    id         INTEGER PRIMARY KEY,
    title      TEXT NOT NULL,
    note       TEXT,
    due        TEXT,                 -- YYYY-MM-DD, or NULL
    high       INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""

MAX_OPEN = 500
# The daily message: its time (Settings, Todos), and the day it last went out.
AT_SETTING = "todos_message_at"
DEFAULT_AT = "08:00"
SENT_SETTING = "todos_message_sent"
LATE = timedelta(hours=2)  # a message missed by more than this (the hub was down) is skipped
MESSAGE_TODOS = 5  # titles in the message, then "and N more"

Title = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
Note = Annotated[str, StringConstraints(strip_whitespace=True, max_length=500)]
Clock = Annotated[str, StringConstraints(pattern=r"^([01]\d|2[0-3]):[0-5]\d$")]


class Draft(BaseModel):
    """A todo as the hub's form (or Claude) sends it."""

    title: Title
    note: Note | None = None
    due: date | None = None
    high: bool = False

    @field_validator("note")
    @classmethod
    def _blank_is_none(cls, note: str | None) -> str | None:
        return note or None


class Todo(Draft):
    id: int
    created: datetime


# --- the store ------------------------------------------------------------------------


_ready: weakref.WeakSet[Store] = weakref.WeakSet()


def ensure_tables(store: Store) -> None:
    """At start-up, and on first use by the panel's answer."""
    if store in _ready:
        return
    with store.connect() as conn:
        conn.executescript(TABLES)
    _ready.add(store)


def _stamp(now: datetime | None) -> str:
    return (now or datetime.now(UTC)).isoformat(timespec="seconds")


def _row(row: Any) -> Todo:
    return Todo(id=row["id"], title=row["title"], note=row["note"],
                due=date.fromisoformat(row["due"]) if row["due"] else None,
                high=bool(row["high"]), created=datetime.fromisoformat(row["created_at"]))


def _sort_key(t: Todo) -> tuple[Any, ...]:
    """High first, then by due date (no date last), then oldest first."""
    return (not t.high, t.due is None, t.due or date.max, t.created, t.id)


def all_todos(store: Store) -> list[Todo]:
    """Every open todo, in the order the hub shows them."""
    with store.connect() as conn:
        rows = conn.execute("SELECT * FROM todo").fetchall()
    return sorted((_row(r) for r in rows), key=_sort_key)


def count(store: Store) -> int:
    with store.connect() as conn:
        return conn.execute("SELECT COUNT(*) FROM todo").fetchone()[0]


def get(store: Store, todo_id: int) -> Todo | None:
    with store.connect() as conn:
        row = conn.execute("SELECT * FROM todo WHERE id = ?", (todo_id,)).fetchone()
    return _row(row) if row else None


def add(store: Store, draft: Draft, now: datetime | None = None) -> Todo:
    at = _stamp(now)
    with store.connect() as conn:
        cur = conn.execute(
            "INSERT INTO todo (title, note, due, high, created_at, updated_at)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (draft.title, draft.note, draft.due.isoformat() if draft.due else None,
             int(draft.high), at, at))
        todo_id = cur.lastrowid
    return Todo(id=todo_id, created=datetime.fromisoformat(at), **draft.model_dump())


def change(store: Store, todo_id: int, draft: Draft, now: datetime | None = None) -> bool:
    with store.connect() as conn:
        cur = conn.execute(
            "UPDATE todo SET title = ?, note = ?, due = ?, high = ?, updated_at = ?"
            " WHERE id = ?",
            (draft.title, draft.note, draft.due.isoformat() if draft.due else None,
             int(draft.high), _stamp(now), todo_id))
    return cur.rowcount == 1


def remove(store: Store, todo_id: int) -> Todo | None:
    """Ticks a todo off (or deletes it: the same thing here). Answers what was removed, for
    Undo, or None when there was no such todo."""
    found = get(store, todo_id)
    if found is None:
        return None
    with store.connect() as conn:
        conn.execute("DELETE FROM todo WHERE id = ?", (todo_id,))
    return found


def restore(store: Store, todo: Todo, now: datetime | None = None) -> bool:
    """Undo: puts a removed todo back with its id and age. False when the id is taken."""
    with store.connect() as conn:
        cur = conn.execute(
            "INSERT OR IGNORE INTO todo (id, title, note, due, high, created_at, updated_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            (todo.id, todo.title, todo.note, todo.due.isoformat() if todo.due else None,
             int(todo.high), todo.created.isoformat(timespec="seconds"), _stamp(now)))
    return cur.rowcount == 1


# --- what the hub and the panel show --------------------------------------------------


def state(t: Draft, day: date) -> str | None:
    """"overdue", "today" or None, from the due date."""
    if t.due is None or t.due > day:
        return None
    return "today" if t.due == day else "overdue"


def overview(store: Store, now: datetime, day: date) -> dict[str, Any]:
    """The Todos page and the Home card: every open todo in order, with its state, and the
    counts the card and the daily message lead with."""
    listed = [t.model_dump(mode="json") | {"state": state(t, day)} for t in all_todos(store)]
    return {"as_of": now.isoformat(), "stale": False, "today": day.isoformat(),
            "open": len(listed),
            "overdue": sum(t["state"] == "overdue" for t in listed),
            "due_today": sum(t["state"] == "today" for t in listed),
            "todos": listed}


# --- the daily ntfy message -----------------------------------------------------------


def message_at(store: Store) -> str:
    """The daily message's time, "08:00" until set."""
    return core.get_setting(store, AT_SETTING, DEFAULT_AT)


def put_message_at(store: Store, at: str) -> str:
    core.put_setting(store, AT_SETTING, at)
    return at


def _late(t: Todo, day: date) -> str:
    if t.due is None or t.due > day:
        return ""
    days = (day - t.due).days
    return " (today)" if days == 0 else " (yesterday)" if days == 1 else f" ({days} days late)"


def message(listed: list[Todo], day: date) -> tuple[str, str]:
    """The ntfy title and text: "4 open todos, 1 overdue", then the first five, each with
    High and how late it is."""
    overdue = sum(state(t, day) == "overdue" for t in listed)
    title = f"{len(listed)} open todo{'' if len(listed) == 1 else 's'}"
    if overdue:
        title += f", {overdue} overdue"
    lines = [f"{'High: ' if t.high else ''}{t.title}{_late(t, day)}"
             for t in listed[:MESSAGE_TODOS]]
    if len(listed) > MESSAGE_TODOS:
        lines.append(f"and {len(listed) - MESSAGE_TODOS} more")
    return title, "\n".join(lines)


def due_message(store: Store, now: datetime, zone: Any) -> date | None:
    """The day whose message goes out now: its time has come in the last two hours, and
    none went out for it yet. None otherwise."""
    local = now.astimezone(zone)
    when = datetime.combine(local.date(), time.fromisoformat(message_at(store)), zone)
    if not when <= now < when + LATE:
        return None
    if core.get_setting(store, SENT_SETTING, None) == local.date().isoformat():
        return None
    return local.date()


async def send_daily(cfg: dict[str, Any], store: Store, now: datetime | None = None) -> bool:
    """Every minute (app/scheduler.py): at the set time, one message with the open todos,
    every day of the week; nothing when none is open. A failed send is tried again the next
    minute. Answers whether one went out."""
    now = now or datetime.now(UTC)
    day = due_message(store, now, config.zone(cfg))
    if day is None:
        return False
    listed = all_todos(store)
    if listed:
        title, body = message(listed, day)
        await core.notify(store, cfg, source="todos", category="todos", severity="info",
                          title=title, body=body, now=now)
    core.put_setting(store, SENT_SETTING, day.isoformat())
    return bool(listed)
