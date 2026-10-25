"""Morning digest (plan.md M26, step 3): the night and the day ahead, in a few lines.

Weekdays at 06:30 the hub gathers its own state from the cache (the backup,
updates since last evening, disks and storage, open alerts, the weather, the
train, the first event, pinned images behind) as short facts and asks Haiku for
one answer in three forms (structured output): a paragraph for Telegram, one
line and four facts for the Now panel's Briefing screen and Home's card. It
shows there until 09:00.

Data sent (plan.md M26): the house's own state, the first event's time and
title only, no other calendar titles and no portfolio amounts.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from pydantic import BaseModel

from . import ai
from .alerts import core, rules, templates
from .store import Store

log = logging.getLogger(__name__)

FEATURE = "briefing"
CACHE_KEY = "briefing"
AT = "06:30"  # local, weekdays
UNTIL = "09:00"  # local: the panel and Home stop showing it
LINE_MAX = 70
FACT_MAX = 30
UPDATES_SINCE = timedelta(hours=14)  # from about 16:30 the day before

SYSTEM = (
    "You write the morning briefing for a household's home server, from facts the server "
    "gathered. Give three forms of the same briefing. `paragraph`: two to four short "
    "sentences for a chat message, warm and plain, starting with \"Good morning.\"; mention "
    "only what is in the facts, problems first, and skip what is unknown. `line`: one short "
    f"sentence of at most {LINE_MAX} characters, the gist. `facts`: exactly four facts of at "
    f"most {FACT_MAX} characters each, the most useful first (a problem, the backup, the "
    "train, the first event, the weather). No markdown, no emoji. Write times as 24-hour "
    "HH:MM."
)

SCHEMA = {
    "type": "object",
    "properties": {
        "paragraph": {"type": "string"},
        "line": {"type": "string"},
        "facts": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["paragraph", "line", "facts"],
    "additionalProperties": False,
}


class Briefing(BaseModel):
    as_of: datetime
    stale: bool = False
    date: str  # the local date it is for, YYYY-MM-DD
    until: datetime  # 09:00 local that day: shown until then
    line: str
    facts: list[str]
    paragraph: str


def _hhmm(value: Any, cfg: dict[str, Any]) -> str | None:
    if not value:
        return None
    return core.local(datetime.fromisoformat(str(value)), cfg).strftime("%H:%M")


def facts(cfg: dict[str, Any], store: Store, now: datetime) -> list[str]:
    """The house's state as short plain facts; only what the cache knows."""
    out: list[str] = []
    today = core.local(now, cfg).date().isoformat()

    nas = store.get_cache("nas") or {}
    backup = nas.get("backup") or {}
    if backup.get("status") in ("ok", "fail", "warn"):
        word = {"ok": "finished", "fail": "FAILED", "warn": "needs a look"}[backup["status"]]
        at = _hhmm(backup.get("at"), cfg)
        out.append(f"Backup to Hetzner: {word}" + (f" at {at}" if at else ""))
    storage = nas.get("storage") or {}
    if storage.get("used_pct") is not None:
        out.append(f"Storage: {round(storage['used_pct'])}% used")
    for pool in storage.get("pools") or []:
        if pool.get("used_pct", 0) >= 90:
            out.append(f"Pool {pool['name']} is {round(pool['used_pct'])}% full")
    bad = [d["name"] for d in nas.get("disks") or [] if d.get("smart") in ("warn", "fail")]
    out.append(f"Disks with SMART warnings: {', '.join(bad)}" if bad else "Disks: all healthy")

    since = (now - UPDATES_SINCE).isoformat()
    updated = sorted({r["name"] for r in store.container_updates(100) if r["ts"] >= since})
    if updated:
        out.append(f"Updated overnight: {', '.join(updated)}")

    for incident in rules.open_incidents(store).values():
        out.append(f"Open {incident['severity']}: {incident['title']}")

    behind = [p for p in (store.get_cache("pinned") or {}).get("pins") or [] if p.get("behind")]
    for p in behind:
        out.append(f"Pinned {p['repo'].split('/')[-1]} at {p['current']}, newest {p['latest']}")

    weather = store.get_cache("weather") or {}
    if weather.get("temperature") is not None:
        out.append(f"Now outside: {weather['temperature']:.0f} °C"
                   + (f", {weather['description']}" if weather.get("description") else ""))
    day = next((d for d in (store.get_cache("forecast") or {}).get("days") or []
                if d.get("date") == today), None)
    if day:
        out.append(f"Today: {day['low']:.0f} to {day['high']:.0f} °C")
        wet = [h["hour"] for h in day.get("hours") or []
               if h["hour"] >= core.local(now, cfg).hour and h["rain_chance"] >= 50]
        out.append(f"Rain likely from {wet[0]:02d}:00" if wet
                   else "Dry today (rain chance under 50%)")

    train = store.get_cache("train") or {}
    run = train.get("train") or {}
    if train.get("date") == today and train.get("mode") == "morning" and run:
        track = run.get("actual_track") or run.get("planned_track")
        state = {"on_time": "on time", "late": f"{run.get('delay_minutes', 0)} min late",
                 "cancelled": "CANCELLED", "not_found": "not in the planner"}[run["status"]]
        out.append(f"Train {train.get('departure')} to {train.get('route', '').split(' to ')[-1]}: "
                   f"{state}" + (f", platform {track}" if track else ""))

    calendar = store.get_cache("calendar") or {}
    if calendar.get("date") == today:
        first = next((e for e in calendar.get("events") or [] if e.get("start")), None)
        if first:
            out.append(f"First event: {_hhmm(first['start'], cfg)} {first['title']}")
        elif not calendar.get("all_day"):
            out.append("No events today")
    return out


def _until(now: datetime, cfg: dict[str, Any]) -> datetime:
    hour, minute = (int(p) for p in UNTIL.split(":"))
    return core.local(now, cfg).replace(hour=hour, minute=minute, second=0, microsecond=0)


async def make(cfg: dict[str, Any], store: Store, now: datetime | None = None,
               claude: ai.ClientFactory | None = None) -> Briefing | None:
    """Today's briefing, or None (switched off, the cap, or no answer)."""
    now = now or datetime.now(UTC)
    local = core.local(now, cfg)
    lines = facts(cfg, store, now)
    prompt = f"{local:%A %d %B %Y}, {local:%H:%M}.\n\nFacts:\n" + "\n".join(f"- {f}" for f in lines)
    answer = await ai.ask(cfg, store, feature=FEATURE, model=ai.SCHEDULED_MODEL, system=SYSTEM,
                          prompt=prompt, max_tokens=2048, schema=SCHEMA, now=now, client=claude)
    if answer is None:
        return None
    try:
        data = json.loads(answer)
    except json.JSONDecodeError:
        log.warning("briefing: the answer is not JSON")
        return None
    return Briefing(
        as_of=now, date=local.date().isoformat(), until=_until(now, cfg),
        line=str(data["line"]).strip()[:LINE_MAX],
        facts=[str(f).strip()[:FACT_MAX] for f in data["facts"] if str(f).strip()][:4],
        paragraph=str(data["paragraph"]).strip())


async def run(cfg: dict[str, Any], store: Store, now: datetime | None = None,
              claude: ai.ClientFactory | None = None, telegram: Any = None) -> Briefing | None:
    """Make today's briefing, keep it for the panel and Home, and send it to Telegram.
    Nothing happens without an answer: yesterday's stays and is no longer shown."""
    now = now or datetime.now(UTC)
    briefing = await make(cfg, store, now, claude)
    if briefing is None:
        return None
    store.put_cache(CACHE_KEY, briefing.model_dump(mode="json"))
    local = core.local(now, cfg)
    sent = templates.message(store, "briefing", {
        "day": f"{local:%A}", "paragraph": briefing.paragraph})
    # 06:30 is still quiet hours; the digest is wanted then, like the train.
    await core.notify(store, cfg, source="briefing", category="briefing", severity="info",
                      title=sent.title, body=sent.body, formatted=sent.html, bypass_quiet=True,
                      now=now, telegram=telegram)
    return briefing
