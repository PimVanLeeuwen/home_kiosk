"""Reminders (plan.md M32): what the owner and partner set in the hub to remember on a day,
for the Door panel, a card on Home and an ntfy message.

A reminder has a title, a date and an optional time, and repeats never, every N days or
weeks, weekly on chosen days, monthly on a day (or the last day), or yearly, counted from
its date. Ticking one off marks that day's occurrence, never the series. Each reminder
chooses its ntfy message: none, at its time (08:00 without one), an hour before, or the
evening before at 20:00; `due` sends each one once.

Titles are personal data: served to the hub and the panels, never logged.
"""

from __future__ import annotations

import calendar
import json
import weakref
from datetime import UTC, date, datetime, time, timedelta
from typing import Annotated, Any, Literal
from zoneinfo import ZoneInfo

from pydantic import BaseModel, Field, StringConstraints, model_validator

from .alerts import core
from .store import Store

TABLES = """
CREATE TABLE IF NOT EXISTS reminder (
    id         INTEGER PRIMARY KEY,
    title      TEXT NOT NULL,
    start      TEXT NOT NULL,        -- the first day, YYYY-MM-DD
    at         TEXT,                 -- "07:30", or NULL for the whole day
    repeat     TEXT NOT NULL,        -- Repeat as JSON
    notify     TEXT NOT NULL,        -- none, at, hour, evening
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS reminder_done (
    reminder_id INTEGER NOT NULL REFERENCES reminder (id) ON DELETE CASCADE,
    day         TEXT NOT NULL,
    done_at     TEXT NOT NULL,
    PRIMARY KEY (reminder_id, day)
);
CREATE TABLE IF NOT EXISTS reminder_sent (
    reminder_id INTEGER NOT NULL REFERENCES reminder (id) ON DELETE CASCADE,
    day         TEXT NOT NULL,
    sent_at     TEXT NOT NULL,
    PRIMARY KEY (reminder_id, day)
);
"""

WHOLE_DAY_AT = time(8, 0)  # "at its time" for a reminder without one
EVENING_AT = time(20, 0)  # "the evening before"
LATE = timedelta(hours=2)  # a message missed by more than this (the hub was down) is not sent
AHEAD_DAYS = 400  # how far `next_day` looks: a yearly one always falls inside


class Repeat(BaseModel):
    kind: Literal["none", "every", "weekly", "monthly", "yearly"] = "none"
    every: Annotated[int, Field(ge=1, le=365)] = 1  # every N ...
    unit: Literal["days", "weeks"] = "days"  # ... days or weeks
    weekdays: list[Annotated[int, Field(ge=0, le=6)]] = []  # Monday 0, for weekly
    day: Annotated[int, Field(ge=1, le=31)] | Literal["last"] = 1  # for monthly

    @model_validator(mode="after")
    def _complete(self) -> Repeat:
        if self.kind == "weekly" and not self.weekdays:
            raise ValueError("a weekly reminder needs at least one day")
        self.weekdays = sorted(set(self.weekdays))
        return self


Notify = Literal["none", "at", "hour", "evening"]
Title = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
Clock = Annotated[str, StringConstraints(pattern=r"^([01]\d|2[0-3]):[0-5]\d$")]


class Draft(BaseModel):
    """A reminder as the hub's form sends it."""

    title: Title
    start: date
    at: Clock | None = None
    repeat: Repeat = Repeat()
    notify: Notify = "at"

    @model_validator(mode="after")
    def _hour_needs_a_time(self) -> Draft:
        if self.notify == "hour" and self.at is None:
            raise ValueError("an hour before needs a time")
        return self


class Reminder(Draft):
    id: int


# --- when a reminder falls ------------------------------------------------------------


def _last_day(year: int, month: int) -> int:
    return calendar.monthrange(year, month)[1]


def occurs(r: Draft, day: date) -> bool:
    """Whether the reminder falls on `day`. A monthly day past the month's end falls on its
    last day (the 31st on 30 April); 29 February falls on the 28th in other years."""
    if day < r.start:
        return False
    rep = r.repeat
    if rep.kind == "none":
        return day == r.start
    if rep.kind == "every":
        step = rep.every * (7 if rep.unit == "weeks" else 1)
        return (day - r.start).days % step == 0
    if rep.kind == "weekly":
        return day.weekday() in rep.weekdays
    last = _last_day(day.year, day.month)
    if rep.kind == "monthly":
        return day.day == (last if rep.day == "last" else min(rep.day, last))
    return day.month == r.start.month and day.day == min(r.start.day, last)  # yearly


def next_day(r: Draft, after: date) -> date | None:
    """The first day from `after` on that the reminder falls, or None when it never will."""
    if r.repeat.kind == "none":
        return r.start if r.start >= after else None
    day = max(after, r.start)
    for _ in range(AHEAD_DAYS):
        if occurs(r, day):
            return day
        day += timedelta(days=1)
    return None


def notify_at(r: Draft, day: date, zone: ZoneInfo) -> datetime | None:
    """When the message for the occurrence on `day` goes out; None for no message."""
    at = time.fromisoformat(r.at) if r.at else None
    if r.notify == "none":
        return None
    if r.notify == "evening":
        return datetime.combine(day - timedelta(days=1), EVENING_AT, zone)
    when = datetime.combine(day, at or WHOLE_DAY_AT, zone)
    return when - timedelta(hours=1) if r.notify == "hour" else when


# --- the store ------------------------------------------------------------------------


_ready: weakref.WeakSet[Store] = weakref.WeakSet()


def ensure_tables(store: Store) -> None:
    """At start-up, and on first use by the Door panel's answer."""
    if store in _ready:
        return
    with store.connect() as conn:
        conn.executescript(TABLES)
    _ready.add(store)


def _stamp(now: datetime | None) -> str:
    return (now or datetime.now(UTC)).isoformat(timespec="seconds")


def _row(row: Any) -> Reminder:
    return Reminder(id=row["id"], title=row["title"], start=date.fromisoformat(row["start"]),
                    at=row["at"], repeat=Repeat(**json.loads(row["repeat"])),
                    notify=row["notify"])


def all_reminders(store: Store) -> list[Reminder]:
    with store.connect() as conn:
        rows = conn.execute("SELECT * FROM reminder ORDER BY id").fetchall()
    return [_row(r) for r in rows]


def get(store: Store, reminder_id: int) -> Reminder | None:
    with store.connect() as conn:
        row = conn.execute("SELECT * FROM reminder WHERE id = ?", (reminder_id,)).fetchone()
    return _row(row) if row else None


def add(store: Store, draft: Draft, now: datetime | None = None) -> Reminder:
    at = _stamp(now)
    with store.connect() as conn:
        cur = conn.execute(
            "INSERT INTO reminder (title, start, at, repeat, notify, created_at, updated_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            (draft.title, draft.start.isoformat(), draft.at, draft.repeat.model_dump_json(),
             draft.notify, at, at))
        reminder_id = cur.lastrowid
    return Reminder(id=reminder_id, **draft.model_dump())


def change(store: Store, reminder_id: int, draft: Draft, now: datetime | None = None) -> bool:
    """Saves the new version; the days ticked off and the messages sent stay, so a changed
    reminder does not notify again for a day it already did."""
    with store.connect() as conn:
        cur = conn.execute(
            "UPDATE reminder SET title = ?, start = ?, at = ?, repeat = ?, notify = ?,"
            " updated_at = ? WHERE id = ?",
            (draft.title, draft.start.isoformat(), draft.at, draft.repeat.model_dump_json(),
             draft.notify, _stamp(now), reminder_id))
    return cur.rowcount == 1


def delete(store: Store, reminder_id: int) -> bool:
    with store.connect() as conn:
        conn.execute("DELETE FROM reminder_done WHERE reminder_id = ?", (reminder_id,))
        conn.execute("DELETE FROM reminder_sent WHERE reminder_id = ?", (reminder_id,))
        cur = conn.execute("DELETE FROM reminder WHERE id = ?", (reminder_id,))
    return cur.rowcount == 1


def set_done(store: Store, reminder_id: int, day: date, done: bool,
             now: datetime | None = None) -> None:
    with store.connect() as conn:
        if done:
            conn.execute("INSERT OR IGNORE INTO reminder_done (reminder_id, day, done_at)"
                         " VALUES (?, ?, ?)", (reminder_id, day.isoformat(), _stamp(now)))
        else:
            conn.execute("DELETE FROM reminder_done WHERE reminder_id = ? AND day = ?",
                         (reminder_id, day.isoformat()))


def _done(store: Store, day: date) -> set[int]:
    with store.connect() as conn:
        return {r["reminder_id"] for r in conn.execute(
            "SELECT reminder_id FROM reminder_done WHERE day = ?", (day.isoformat(),))}


# --- what the hub and the panels show -------------------------------------------------


def today(store: Store, day: date) -> list[dict[str, Any]]:
    """The day's reminders, the ones with a time first by time, then the rest by title."""
    done = _done(store, day)
    found = [{"id": r.id, "title": r.title, "at": r.at, "done": r.id in done}
             for r in all_reminders(store) if occurs(r, day)]
    return sorted(found, key=lambda r: (r["at"] is None, r["at"] or "", r["title"].lower()))


def overview(store: Store, now: datetime, zone: ZoneInfo) -> dict[str, Any]:
    """The Reminders page: every reminder with the next day it falls, nearest first (those
    that will not fall again last), and today's."""
    day = now.astimezone(zone).date()
    listed = []
    for r in all_reminders(store):
        upcoming = next_day(r, day)
        listed.append(r.model_dump(mode="json") | {
            "next": upcoming.isoformat() if upcoming else None})
    listed.sort(key=lambda r: (r["next"] is None, r["next"] or "", r["at"] or "",
                               r["title"].lower()))
    return {"as_of": now.isoformat(), "stale": False, "today": day.isoformat(),
            "due": today(store, day), "reminders": listed}


# --- the ntfy messages ----------------------------------------------------------------


def due(store: Store, now: datetime, zone: ZoneInfo) -> list[tuple[Reminder, date]]:
    """The messages to send now: their time has come in the last two hours, the day is not
    ticked off, and none went out for it yet. Today's and tomorrow's occurrences (the
    evening before) are looked at."""
    local = now.astimezone(zone).date()
    with store.connect() as conn:
        sent = {(r["reminder_id"], r["day"]) for r in conn.execute(
            "SELECT reminder_id, day FROM reminder_sent WHERE day >= ?", (local.isoformat(),))}
    found = []
    for r in all_reminders(store):
        for day in (local, local + timedelta(days=1)):
            when = notify_at(r, day, zone) if occurs(r, day) else None
            if when is None or not when <= now < when + LATE or (r.id, day.isoformat()) in sent:
                continue
            if r.id not in _done(store, day):
                found.append((r, day))
    return found


def mark_sent(store: Store, reminder_id: int, day: date, now: datetime | None = None) -> None:
    with store.connect() as conn:
        conn.execute("INSERT OR IGNORE INTO reminder_sent (reminder_id, day, sent_at)"
                     " VALUES (?, ?, ?)", (reminder_id, day.isoformat(), _stamp(now)))


def message(r: Reminder, day: date, now: datetime, zone: ZoneInfo) -> tuple[str, str]:
    """The ntfy title and line for an occurrence."""
    local = now.astimezone(zone).date()
    when = "Today" if day == local else "Tomorrow" if day == local + timedelta(days=1) \
        else day.strftime("%a %-d %b")
    return r.title, f"{when} at {r.at}" if r.at else when


async def send_due(cfg: dict[str, Any], store: Store, now: datetime | None = None) -> int:
    """Sends the messages whose time has come (every minute, app/scheduler.py), each once;
    a failed send is tried again the next minute. Answers how many went out."""
    now = now or datetime.now(UTC)
    zone = ZoneInfo(cfg.get("timezone", "UTC"))
    sent = 0
    for r, day in due(store, now, zone):
        title, line = message(r, day, now, zone)
        await core.notify(store, cfg, source="reminders", category="reminders",
                          severity="info", title=title, body=line, now=now)
        mark_sent(store, r.id, day, now)
        sent += 1
    return sent
