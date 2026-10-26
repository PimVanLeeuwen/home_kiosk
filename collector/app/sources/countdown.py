"""Countdowns (plan.md M27, K): the calendar events you mark with "⏳" or "#countdown" in
their title, over the next year, nearest first, for the Now panel's countdown.

The same calendars as the agenda (app/sources/agenda.py: the ones shown in Settings), read
once an hour over a year instead of today; the subscriptions come from the agenda's feed
cache. Titles are personal data: served to the hub, never logged; the marker is left out.
"""

from __future__ import annotations

import asyncio
import logging
import re
from datetime import UTC, date, datetime, timedelta
from typing import Any

import httpx
import recurring_ical_events

from ..models import Envelope
from ..store import Store
from . import agenda

log = logging.getLogger(__name__)

CACHE_KEY = "countdown"
MARKERS = ("⏳", "#countdown")
MARKER = re.compile("|".join(re.escape(m) for m in MARKERS), re.IGNORECASE)
AHEAD = 365  # days
KEEP = 3


class Countdown(Envelope):
    events: list[dict[str, Any]]  # {title, date (YYYY-MM-DD), colour, calendar}, nearest first
    # How many events each of the next seven days holds, for the week view (plan.md M27, J).
    per_day: dict[str, int] = {}
    per_day_colours: dict[str, list[str]] = {}  # their calendars' colours, at most three


def marked(title: str) -> str | None:
    """The title without its marker, or None when it carries none."""
    lowered = title.lower()
    if not any(m in lowered for m in MARKERS):
        return None
    title = MARKER.sub("", title)
    return " ".join(title.split()) or "(no title)"


def found(calendars: list[Any], info: agenda.CalendarInfo, start: datetime,
          end: datetime, week: dict[str, list[str]] | None = None) -> list[dict[str, Any]]:
    """The marked events between start and end; every event of the first week counted into
    `week` (date to its calendars' colours) on the way."""
    out = []
    first_week = start + timedelta(days=7)
    for cal in calendars:
        for event in recurring_ical_events.of(cal).between(start, end):
            if str(event.get("STATUS", "")).upper() == "CANCELLED":
                continue
            begin = event.get("DTSTART").dt
            day = begin.date() if isinstance(begin, datetime) else begin
            if week is not None and day < first_week.date():
                week.setdefault(day.isoformat(), []).append(info.color)
            title = marked(str(event.get("SUMMARY", "")).strip())
            if title is None:
                continue
            out.append({"title": title, "date": day.isoformat(), "colour": info.color,
                        "calendar": info.name})
    return out


async def collect(cfg: dict[str, Any], store: Store, now: datetime | None = None,
                  reader: agenda.Reader | None = None) -> Countdown:
    s = agenda.settings(cfg)
    reader = reader or agenda.READER
    now = now or datetime.now(UTC)
    tz = s["timezone"]
    today = now.astimezone(tz).date()
    start, _ = agenda._day_bounds(today, tz)
    end = start + timedelta(days=AHEAD)
    off = agenda.hidden(store)
    events: list[dict[str, Any]] = []
    async with httpx.AsyncClient(auth=s["auth"], timeout=agenda.TIMEOUT_SECONDS,
                                 transport=reader.transport) as client:
        calendars = await reader.calendar_list(client, s["server"], now)
        shown = [(info, url) for info, url in calendars if info.id not in off]

        week: dict[str, list[str]] = {}

        async def one(info: agenda.CalendarInfo, url: str) -> list[dict[str, Any]]:
            if info.kind == "subscribed":
                data = [await reader.feed(client, info, url, now)]
            else:
                answer = await agenda._dav(client, "REPORT", url, "1",
                                           agenda._report(today, tz, AHEAD))
                data = agenda.parse_report(answer)
            return found(data, info, start, end, week)

        results = await asyncio.gather(*(one(i, u) for i, u in shown), return_exceptions=True)
    for (info, _), result in zip(shown, results, strict=True):
        if isinstance(result, BaseException):
            log.warning("countdown: calendar %s failed: %s", info.id[:8], type(result).__name__)
        else:
            events += result
    events = sorted((e for e in events if date.fromisoformat(e["date"]) >= today),
                    key=lambda e: e["date"])
    return Countdown(as_of=now, stale=False, events=events[:KEEP],
                     per_day={d: len(c) for d, c in week.items()},
                     per_day_colours={d: c[:3] for d, c in week.items()})
