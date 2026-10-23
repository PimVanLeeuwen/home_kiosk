"""Today's calendar: the Home card in the hub and the Now panel's calendar card.

iCloud over CalDAV with an app-specific password (NAS-only .env), read-only.
iCloud holds two kinds of calendar: its own (events served over CalDAV) and
subscriptions to an outside .ics address (GEWIS, Runna, the Harry List; iCloud
only stores the address). Both are read: the own ones with a CalDAV REPORT for
today, the subscriptions by fetching their feed, every 15 minutes at most.
Repeating events are unfolded for today with recurring-ical-events.

The subscription addresses often carry a private token: they are kept in
memory only, never logged and never in an API answer. Event titles are
personal data: served to the hub, never logged.
"""

from __future__ import annotations

import asyncio
import logging
import xml.etree.ElementTree as ET
from datetime import UTC, date, datetime, time, timedelta
from typing import Any, Literal
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

import httpx
import icalendar
import recurring_ical_events
from pydantic import BaseModel

from ..models import Envelope
from ..store import Store

log = logging.getLogger(__name__)

CACHE_KEY = "calendar"
LIST_EVERY = timedelta(hours=1)
FEED_EVERY = timedelta(minutes=15)
TIMEOUT_SECONDS = 15
XML = {"Content-Type": "application/xml; charset=utf-8"}
NS = {"d": "DAV:", "c": "urn:ietf:params:xml:ns:caldav", "cs": "http://calendarserver.org/ns/",
      "a": "http://apple.com/ns/ical/"}

TABLES = """
CREATE TABLE IF NOT EXISTS calendar_hidden (
    calendar_id TEXT PRIMARY KEY  -- the last part of its CalDAV address
);
"""


class CalendarInfo(BaseModel):
    id: str
    name: str
    color: str  # "#ff8d28"
    kind: Literal["icloud", "subscribed"]
    shown: bool = True


class CalendarEvent(BaseModel):
    calendar_id: str
    calendar: str
    color: str
    title: str
    start: datetime | None  # None for an all-day event
    end: datetime | None
    all_day: bool = False


class Tomorrow(BaseModel):
    date: str
    events: list[CalendarEvent]  # timed, by start
    all_day: list[CalendarEvent]


class Today(Envelope):
    date: str  # the local date, YYYY-MM-DD
    events: list[CalendarEvent]  # timed, by start
    all_day: list[CalendarEvent]
    errors: dict[str, str] = {}  # calendar name -> a short reason
    # Read since 2026-10-23 for the Now panel, which shows it once today has nothing left.
    tomorrow: Tomorrow | None = None


def ensure_tables(store: Store) -> None:
    with store.connect() as conn:
        conn.executescript(TABLES)


def settings(cfg: dict[str, Any]) -> dict[str, Any]:
    cal = cfg.get("calendar") or {}
    user = (cal.get("username") or "").strip()
    password = (cal.get("app_password") or "").strip()
    return {"enabled": bool(user and password), "auth": (user, password),
            "server": cal.get("server") or "https://caldav.icloud.com",
            "timezone": ZoneInfo(cfg.get("timezone", "Europe/Amsterdam"))}


def hidden(store: Store) -> set[str]:
    with store.connect() as conn:
        return {r["calendar_id"] for r in conn.execute("SELECT calendar_id FROM calendar_hidden")}


def set_shown(store: Store, calendar_id: str, shown: bool) -> None:
    with store.connect() as conn:
        if shown:
            conn.execute("DELETE FROM calendar_hidden WHERE calendar_id = ?", (calendar_id,))
        else:
            conn.execute("INSERT OR IGNORE INTO calendar_hidden (calendar_id) VALUES (?)",
                         (calendar_id,))


# --- the calendar list --------------------------------------------------------------


def _colour(value: str | None) -> str:
    """Apple writes "#FF8D28FF" (with alpha); the hub wants "#ff8d28"."""
    if not value or not value.startswith("#") or len(value) < 7:
        return "#8f80ff"
    return value[:7].lower()


def parse_calendars(xml: str) -> list[tuple[CalendarInfo, str]]:
    """Each calendar with where to read it: its CalDAV address (own) or its
    feed address (subscribed). Task lists and iCloud's inbox, outbox and
    notifications are left out."""
    found = []
    for resp in ET.fromstring(xml).iterfind("d:response", NS):
        href = (resp.findtext("d:href", "", NS) or "").strip()
        kinds = {child.tag for child in resp.iterfind(".//d:resourcetype/*", NS)}
        name = (resp.findtext(".//d:displayname", "", NS) or "").strip()
        colour = _colour(resp.findtext(".//a:calendar-color", None, NS))
        cal_id = href.rstrip("/").rsplit("/", 1)[-1]
        if f"{{{NS['cs']}}}subscribed" in kinds:
            source = (resp.findtext(".//cs:source/d:href", "", NS) or "").strip()
            if source:
                url = source.replace("webcal://", "https://", 1)
                found.append((CalendarInfo(id=cal_id, name=name, color=colour, kind="subscribed"),
                              url))
        elif f"{{{NS['c']}}}calendar" in kinds:
            comps = {c.get("name") for c in
                     resp.iterfind(".//c:supported-calendar-component-set/c:comp", NS)}
            if comps and "VEVENT" not in comps:
                continue  # a task list (Reminders)
            found.append((CalendarInfo(id=cal_id, name=name, color=colour, kind="icloud"), href))
    return found


def _href(xml: str, element: str) -> str:
    node = ET.fromstring(xml).find(f".//{element}/d:href", NS)
    if node is None or not (node.text or "").strip():
        raise ValueError(f"no {element} in the answer")
    return node.text.strip()


async def _dav(client: httpx.AsyncClient, method: str, url: str, depth: str, body: str) -> str:
    resp = await client.request(method, url, content=body, headers=XML | {"Depth": depth})
    resp.raise_for_status()
    return resp.text


PRINCIPAL = '<d:propfind xmlns:d="DAV:"><d:prop><d:current-user-principal/></d:prop></d:propfind>'
HOME = ('<d:propfind xmlns:d="DAV:" xmlns:c="urn:ietf:params:xml:ns:caldav"><d:prop>'
        '<c:calendar-home-set/></d:prop></d:propfind>')
LIST = ('<d:propfind xmlns:d="DAV:" xmlns:c="urn:ietf:params:xml:ns:caldav" '
        'xmlns:cs="http://calendarserver.org/ns/" xmlns:a="http://apple.com/ns/ical/"><d:prop>'
        '<d:displayname/><d:resourcetype/><a:calendar-color/><cs:source/>'
        '<c:supported-calendar-component-set/></d:prop></d:propfind>')


async def list_calendars(client: httpx.AsyncClient, server: str) -> list[tuple[CalendarInfo, str]]:
    principal = _href(await _dav(client, "PROPFIND", f"{server}/", "0", PRINCIPAL),
                      "d:current-user-principal")
    home = _href(await _dav(client, "PROPFIND", f"{server}{principal}", "0", HOME),
                 "c:calendar-home-set")
    if not home.startswith("http"):
        home = f"{server}{home}"
    found = parse_calendars(await _dav(client, "PROPFIND", home, "1", LIST))
    base = "{0.scheme}://{0.netloc}".format(urlsplit(home))
    return [(info, url if info.kind == "subscribed" else f"{base}{url}") for info, url in found]


# --- today's events ------------------------------------------------------------------


def _day_bounds(day: date, tz: ZoneInfo) -> tuple[datetime, datetime]:
    start = datetime.combine(day, time(0), tz)
    return start, start + timedelta(days=1)


def events_today(calendars: list[icalendar.Calendar], info: CalendarInfo, day: date,
                 tz: ZoneInfo) -> list[CalendarEvent]:
    """Today's occurrences in one calendar's iCalendar data, repeating events
    unfolded. Times without a zone count as local."""
    start, end = _day_bounds(day, tz)
    found = []
    for cal in calendars:
        for event in recurring_ical_events.of(cal).between(start, end):
            if str(event.get("STATUS", "")).upper() == "CANCELLED":
                continue
            begin = event.get("DTSTART").dt
            finish = event.get("DTEND").dt if event.get("DTEND") else None
            title = str(event.get("SUMMARY", "")).strip() or "(no title)"
            if not isinstance(begin, datetime):  # all day
                found.append(CalendarEvent(calendar_id=info.id, calendar=info.name,
                                           color=info.color, title=title, start=None, end=None,
                                           all_day=True))
                continue
            begin = begin if begin.tzinfo else begin.replace(tzinfo=tz)
            if finish is not None and isinstance(finish, datetime) and not finish.tzinfo:
                finish = finish.replace(tzinfo=tz)
            stop = finish.astimezone(tz) if isinstance(finish, datetime) else None
            found.append(CalendarEvent(calendar_id=info.id, calendar=info.name, color=info.color,
                                       title=title, start=begin.astimezone(tz), end=stop))
    return found


def _report(day: date, tz: ZoneInfo, days: int = 1) -> str:
    start, _ = _day_bounds(day, tz)
    end = start + timedelta(days=days)
    stamp = "%Y%m%dT%H%M%SZ"
    return ('<c:calendar-query xmlns:d="DAV:" xmlns:c="urn:ietf:params:xml:ns:caldav"><d:prop>'
            '<c:calendar-data/></d:prop><c:filter><c:comp-filter name="VCALENDAR">'
            '<c:comp-filter name="VEVENT">'
            f'<c:time-range start="{start.astimezone(UTC).strftime(stamp)}" '
            f'end="{end.astimezone(UTC).strftime(stamp)}"/>'
            '</c:comp-filter></c:comp-filter></c:filter></c:calendar-query>')


def parse_report(xml: str) -> list[icalendar.Calendar]:
    return [icalendar.Calendar.from_ical(node.text)
            for node in ET.fromstring(xml).iterfind(".//c:calendar-data", NS) if node.text]


class Reader:
    """Keeps the calendar list (with the addresses, in memory only) and the
    subscription feeds between runs, so neither is fetched every 5 minutes."""

    def __init__(self, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self.transport = transport  # for tests
        self.calendars: list[tuple[CalendarInfo, str]] = []
        self.listed_at: datetime | None = None
        self.feeds: dict[str, tuple[datetime, icalendar.Calendar]] = {}

    async def calendar_list(self, client: httpx.AsyncClient, server: str,
                            now: datetime) -> list[tuple[CalendarInfo, str]]:
        if not self.calendars or not self.listed_at or now - self.listed_at > LIST_EVERY:
            self.calendars = await list_calendars(client, server)
            self.listed_at = now
        return self.calendars

    async def feed(self, client: httpx.AsyncClient, info: CalendarInfo, url: str,
                   now: datetime) -> icalendar.Calendar:
        kept = self.feeds.get(info.id)
        if kept and now - kept[0] < FEED_EVERY:
            return kept[1]
        # A plain client: the feed's own host, without the iCloud login.
        async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS, follow_redirects=True,
                                     transport=self.transport) as plain:
            resp = await plain.get(url)
            resp.raise_for_status()
        cal = icalendar.Calendar.from_ical(resp.content)
        self.feeds[info.id] = (now, cal)
        return cal


READER = Reader()


def _reason(exc: BaseException) -> str:
    if isinstance(exc, httpx.HTTPStatusError):
        code = exc.response.status_code
        return "login refused" if code in (401, 403) else f"HTTP {code}"
    if isinstance(exc, httpx.TimeoutException):
        return "timed out"
    if isinstance(exc, httpx.ConnectError):
        return "not reachable"
    return "unreadable answer"


async def collect(cfg: dict[str, Any], store: Store, now: datetime | None = None,
                  reader: Reader | None = None) -> Today:
    """Raises when the calendar list cannot be read, so the last good answer
    stays cached, flagged stale; one calendar failing only notes it."""
    s = settings(cfg)
    reader = reader or READER
    now = now or datetime.now(UTC)
    day = now.astimezone(s["timezone"]).date()
    off = hidden(store)
    events: list[CalendarEvent] = []
    later: list[CalendarEvent] = []
    errors: dict[str, str] = {}
    async with httpx.AsyncClient(auth=s["auth"], timeout=TIMEOUT_SECONDS,
                                 transport=reader.transport) as client:
        calendars = await reader.calendar_list(client, s["server"], now)
        shown = [(info, url) for info, url in calendars if info.id not in off]

        async def one(info: CalendarInfo, url: str) -> tuple[list[CalendarEvent], ...]:
            if info.kind == "subscribed":
                data = [await reader.feed(client, info, url, now)]
            else:  # today and tomorrow in one query, split below
                answer = await _dav(client, "REPORT", url, "1", _report(day, s["timezone"], 2))
                data = parse_report(answer)
            return (events_today(data, info, day, s["timezone"]),
                    events_today(data, info, day + timedelta(days=1), s["timezone"]))

        results = await asyncio.gather(*(one(i, u) for i, u in shown), return_exceptions=True)
    for (info, _), result in zip(shown, results, strict=True):
        if isinstance(result, BaseException):
            # The class only: errors can carry the address, and the address a token.
            log.warning("calendar %s failed: %s", info.id[:8], type(result).__name__)
            errors[info.name] = _reason(result)
        else:
            events += result[0]
            later += result[1]
    timed = sorted((e for e in events if not e.all_day), key=lambda e: e.start)
    return Today(as_of=now, stale=False, date=day.isoformat(), events=timed,
                 all_day=[e for e in events if e.all_day], errors=errors,
                 tomorrow=Tomorrow(date=(day + timedelta(days=1)).isoformat(),
                                   events=sorted((e for e in later if not e.all_day),
                                                 key=lambda e: e.start),
                                   all_day=[e for e in later if e.all_day]))


def calendar_list(store: Store, reader: Reader | None = None) -> list[CalendarInfo]:
    """For Settings: every calendar with its switch, without any addresses."""
    off = hidden(store)
    return [info.model_copy(update={"shown": info.id not in off})
            for info, _ in (reader or READER).calendars]
