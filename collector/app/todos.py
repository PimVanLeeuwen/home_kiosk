"""Todos (plan.md M37): what the owner wants done, kept until it is, for the Todos page, a
card on Home, the Now panel, a daily ntfy message and Claude.

A todo has a title, and optionally a short note, a due date and a High flag. Ticking one off
removes it; the hub's Undo puts it back as it was (`restore`, same id and age), so there is
no Done list and no history.

Titles and notes are personal data: served to the hub, the panel and the MCP tools, never
logged.
"""

from __future__ import annotations

import weakref
from datetime import UTC, date, datetime
from typing import Annotated, Any

from pydantic import BaseModel, StringConstraints, field_validator

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

Title = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
Note = Annotated[str, StringConstraints(strip_whitespace=True, max_length=500)]


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
