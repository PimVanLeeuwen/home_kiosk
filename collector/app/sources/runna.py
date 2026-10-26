"""Runna's plan (plan.md M28, step 2): the training sessions from Runna's Calendar Sync, an
iCalendar feed. Read hourly: the sessions of this week and the next eight, with the next one
first, and the race when the plan has one.

Runna's events, as seen in its feed (not documented by Runna):
    SUMMARY:🏃 Threshold Intervals • 5mi
    DESCRIPTION:Intervals • 5mi • 45m - 50m\\n\\n1mi warm up ...\\n\\n📲 View in the Runna app: …
    DTSTART;VALUE=DATE:20260401 (all day, unless the workout was given a time)
    X-WORKOUT-ESTIMATED-DURATION:3000
    UID:UPCOMING_PLAN_WORKOUT-…
Distances come in the units chosen in Runna (km or mi) and are kept in metres. The feed's
address is a secret (`running.runna_feed`, NAS-only `RUNNA_ICS_URL`): never logged or served.
"""

from __future__ import annotations

import re
from datetime import UTC, date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import httpx
import icalendar
from pydantic import BaseModel

from ..models import Envelope
from ..panel_text import latin1
from ..store import Store

CACHE_KEY = "runna"
AHEAD_DAYS = 63
TIMEOUT_SECONDS = 20
MAX_STEPS = 12
DISTANCE = re.compile(r"(\d+(?:[.,]\d+)?)\s*(km|mi|m)\b", re.IGNORECASE)
TO_METRES = {"km": 1000.0, "mi": 1609.344, "m": 1.0}
# "Race Day", "Half Marathon"; not "Race Pace Intervals" or "Marathon Pace Run".
RACE = re.compile(r"\b(race|marathon)\b(?!\s*pace)", re.IGNORECASE)


class Session(BaseModel):
    uid: str
    date: str                # YYYY-MM-DD, local
    time: str | None         # HH:MM when the workout has a time of day
    name: str                # "Threshold Intervals"
    kind: str | None         # "Intervals", "Easy Run", "Long Run", from the description
    distance_m: float | None
    estimate: str | None     # "45m - 50m", Runna's own wording
    estimate_s: int | None
    steps: list[str] = []    # the description's lines, warm-up to cool-down
    race: bool = False


class Plan(Envelope):
    sessions: list[Session]  # today on, nearest first
    week: list[dict[str, Any]] = []  # Monday to Sunday: {date, planned_m, sessions}
    race: Session | None = None


def settings(cfg: dict[str, Any]) -> dict[str, Any]:
    url = ((cfg.get("running") or {}).get("runna_feed") or "").strip()
    if url.startswith("webcal://"):
        url = "https://" + url[len("webcal://"):]
    return {"enabled": url.startswith("https://"), "url": url,
            "timezone": ZoneInfo(cfg.get("timezone", "Europe/Amsterdam"))}


def metres(text: str) -> float | None:
    """The first distance in a text: "5mi", "8 km", "400m"."""
    found = DISTANCE.search(text or "")
    if not found:
        return None
    return round(float(found.group(1).replace(",", ".")) * TO_METRES[found.group(2).lower()], 1)


def _name(summary: str) -> str:
    """"🏃 6.5mi Long Run • 6.5mi" as "6.5mi Long Run": no emoji, no distance after the dot."""
    name = summary.split("•")[0]
    name = re.sub(r"^[^\w(]+", "", name).strip()
    return name or "Run"


def _steps(description: str) -> tuple[str | None, str | None, list[str]]:
    """The kind and the expected time from the first line, and the steps after it."""
    lines = [line.strip() for line in description.replace("\r", "").split("\n")]
    head = lines[0].split("•") if lines else []
    kind = (head[0].strip() or None) if head else None
    estimate = (head[2].strip() or None) if len(head) > 2 else None
    steps = [line.lstrip("• ").strip() for line in lines[1:]
             if line and not line.startswith("📲") and not set(line) <= {"-"}]
    return kind, estimate, steps[:MAX_STEPS]


def parse(ics: str, tz: ZoneInfo) -> list[Session]:
    sessions = []
    for event in icalendar.Calendar.from_ical(ics).walk("VEVENT"):
        start = event.get("DTSTART")
        if start is None:
            continue
        begin = start.dt
        timed = isinstance(begin, datetime)
        local = begin.astimezone(tz) if timed and begin.tzinfo else begin
        day = local.date() if timed else begin
        summary = str(event.get("SUMMARY") or "")
        kind, estimate, steps = _steps(str(event.get("DESCRIPTION") or ""))
        try:
            estimate_s = int(str(event.get("X-WORKOUT-ESTIMATED-DURATION")))
        except ValueError:
            estimate_s = None
        name = _name(summary)
        sessions.append(Session(
            uid=str(event.get("UID") or f"{day}-{name}"), date=day.isoformat(),
            time=local.strftime("%H:%M") if timed else None,
            name=latin1(name), kind=latin1(kind) if kind else None,
            distance_m=metres(summary.split("•")[-1]) or metres(summary),
            estimate=estimate, estimate_s=estimate_s,
            steps=[latin1(s) for s in steps], race=bool(RACE.search(name))))
    return sorted(sessions, key=lambda s: (s.date, s.time or ""))


def plan(sessions: list[Session], today: date) -> Plan:
    upcoming = [s for s in sessions if today.isoformat() <= s.date
                <= (today + timedelta(days=AHEAD_DAYS)).isoformat()]
    monday = today - timedelta(days=today.weekday())
    week = []
    for i in range(7):
        day = (monday + timedelta(days=i)).isoformat()
        on = [s for s in sessions if s.date == day]
        week.append({"date": day, "planned_m": sum(s.distance_m or 0 for s in on),
                     "sessions": [s.name for s in on]})
    race = next((s for s in sessions if s.race and s.date >= today.isoformat()), None)
    return Plan(as_of=datetime.now(UTC), stale=False, sessions=upcoming, week=week, race=race)


async def collect(cfg: dict[str, Any], store: Store, now: datetime | None = None,
                  transport: httpx.AsyncBaseTransport | None = None) -> Plan:
    s = settings(cfg)
    now = now or datetime.now(UTC)
    # httpx's errors name the URL, which is a secret: the log gets the status or the kind only.
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS, follow_redirects=True,
                                     transport=transport) as client:
            resp = await client.get(s["url"])
    except httpx.HTTPError as exc:
        raise RuntimeError(f"Runna's feed could not be reached ({type(exc).__name__})") from None
    if resp.status_code != 200:
        raise RuntimeError(f"Runna's feed answered {resp.status_code}")
    found = plan(parse(resp.text, s["timezone"]), now.astimezone(s["timezone"]).date())
    return found.model_copy(update={"as_of": now})
