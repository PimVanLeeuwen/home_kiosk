"""Morning digest (plan.md M26 step 3, M29): the night and the day ahead.

Weekdays at 06:30 the hub turns its cache into labelled items in two sections,
your day (the train and works on its route, today's agenda, the weather) and
the house (open alerts, the backup, storage, disks, updates since last evening,
pinned images behind). Telegram gets them as they are, under an opening Sonnet
writes (structured output), which also gives one line and four facts for the
Now panel's Briefing screen and Home's card. It shows there until 09:00.

Markets (the portfolio, with notes on the big movers) and News (the top
stories as the hub already has them) are added by the hub, after your day.

Data sent (plan.md M26, M29): the same items, but of the agenda only the first
event's time and title; no other calendar titles and no portfolio amounts.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from pydantic import BaseModel

from . import ai, explain_open
from .alerts import core, rules, templates
from .portfolio import notes as market_notes
from .portfolio import report
from .portfolio.moves import day_move
from .store import Store

log = logging.getLogger(__name__)

FEATURE = "briefing"
CACHE_KEY = "briefing"
AT = "06:30"  # local, weekdays
UNTIL = "09:00"  # local: the panel and Home stop showing it
OPENING_MAX = 280
LINE_MAX = 70
FACT_MAX = 30
UPDATES_SINCE = timedelta(hours=14)  # from about 16:30 the day before
STORIES = 3
NEWS_FRESH = timedelta(hours=12)  # the night's last headlines, from about 23:00, still count

SYSTEM = (
    "You write the opening of a household's morning briefing, from facts its home server "
    "gathered. The message lists every fact under your opening, so do not repeat them all. "
    "Give three forms. `opening`: one or two short sentences, at most "
    f"{OPENING_MAX} characters, on what matters most today: a problem first (the train late "
    "or cancelled, works on its route, a failed backup, an open warning and what it means), "
    "otherwise the train and when it rains; a quiet morning may simply say so. Do not start "
    "with a greeting. `line`: one short sentence of at most "
    f"{LINE_MAX} characters, the gist. `facts`: exactly four facts of at most {FACT_MAX} "
    "characters each, the most useful first (a problem, the backup, the train, the first "
    "event, the weather). Mention only what is in the facts and skip what is unknown. Plain "
    "and warm, no markdown, no emoji. Write times as 24-hour HH:MM."
)

SCHEMA = {
    "type": "object",
    "properties": {
        "opening": {"type": "string"},
        "line": {"type": "string"},
        "facts": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["opening", "line", "facts"],
    "additionalProperties": False,
}

# One line of a section: a short label and its text, e.g. ("Backup", "finished at 03:41").
Item = tuple[str, str]


class Briefing(BaseModel):
    as_of: datetime
    stale: bool = False
    date: str  # the local date it is for, YYYY-MM-DD
    until: datetime  # 09:00 local that day: shown until then
    line: str
    facts: list[str]
    paragraph: str  # Claude's opening (a whole paragraph before M29)


def _hhmm(value: Any, cfg: dict[str, Any]) -> str | None:
    if not value:
        return None
    return core.local(datetime.fromisoformat(str(value)), cfg).strftime("%H:%M")


def _train(cfg: dict[str, Any], store: Store, today: str) -> list[Item]:
    """This morning's train and works or disruptions on its route. Only the
    morning's own check: an evening "tomorrow" alert never reaches the briefing."""
    train = store.get_cache("train") or {}
    run = train.get("train")
    if train.get("date") != today or train.get("mode") != "morning":
        return []
    where = train.get("route", "").split(" to ")[-1]
    head = f"{train.get('departure')} to {where}"
    out: list[Item] = []
    if run is None or run.get("status") in ("cancelled", "not_found"):
        gone = "is CANCELLED" if run and run["status"] == "cancelled" else "is not in NS's planner"
        out.append(("Train", f"{head} {gone}"))
        out.append(("Instead", rules._next_text(train.get("next_direct")).rstrip(".")))
    else:
        planned, actual = run.get("planned_track"), run.get("actual_track")
        state = (f"{run.get('delay_minutes', 0)} min late, leaves "
                 f"{_hhmm(run.get('actual_departure'), cfg) or train.get('departure')}"
                 if run["status"] == "late" else "on time")
        track = actual or planned
        where_from = (f", platform {track}" if track else "") + (
            f" (not {planned})" if planned and actual and planned != actual else "")
        out.append(("Train", f"{head}, {state}{where_from}"))
        skipped = [stop["name"] for stop in (run.get("stops") or [])[1:] if stop.get("cancelled")]
        if skipped:
            out.append(("Skips", ", ".join(skipped)))
    for item in train.get("disruptions") or []:
        label = "Works" if item.get("kind") == "MAINTENANCE" else "Disruption"
        text = " ".join(t for t in (item.get("text") or item.get("title"), item.get("until"))
                        if t)
        out.append((label, f"on your route: {text}"))
    return out


def _agenda(cfg: dict[str, Any], store: Store, today: str, full: bool) -> list[Item]:
    """Today's events; with `full` False only the first one (what Claude may see)."""
    calendar = store.get_cache("calendar") or {}
    if calendar.get("date") != today:
        return []
    timed = [e for e in calendar.get("events") or [] if e.get("start")]
    if not full:
        if timed:
            return [("First event", f"{_hhmm(timed[0]['start'], cfg)} {timed[0]['title']}")]
        return [] if calendar.get("all_day") else [("Agenda", "no events today")]
    out: list[Item] = [("All day", e["title"]) for e in calendar.get("all_day") or []]
    out += [(_hhmm(e["start"], cfg) or "", e["title"]) for e in timed]
    return out or [("Agenda", "no events today")]


def _weather(cfg: dict[str, Any], store: Store, now: datetime, today: str) -> list[Item]:
    parts = []
    weather = store.get_cache("weather") or {}
    if weather.get("temperature") is not None:
        parts.append(f"{weather['temperature']:.0f} °C now"
                     + (f", {weather['description']}" if weather.get("description") else ""))
    day = next((d for d in (store.get_cache("forecast") or {}).get("days") or []
                if d.get("date") == today), None)
    if day:
        parts.append(f"{day['low']:.0f} to {day['high']:.0f} °C today")
        wet = [h["hour"] for h in day.get("hours") or []
               if h["hour"] >= core.local(now, cfg).hour and h["rain_chance"] >= 50]
        parts.append(f"rain likely from {wet[0]:02d}:00" if wet
                     else "dry (rain chance under 50%)")
    return [("Weather", "; ".join(parts))] if parts else []


def your_day(cfg: dict[str, Any], store: Store, now: datetime, full: bool = True) -> list[Item]:
    today = core.local(now, cfg).date().isoformat()
    return (_train(cfg, store, today) + _agenda(cfg, store, today, full)
            + _weather(cfg, store, now, today))


def house(cfg: dict[str, Any], store: Store, now: datetime) -> list[Item]:
    """The house's state, open problems first. Train alerts are left out: your day
    has the train from this morning's own check."""
    out: list[Item] = [(core.LEVEL.get(i["severity"], "Open"), i["title"])
                       for i in explain_open.open_alerts(store)]

    nas = store.get_cache("nas") or {}
    backup = nas.get("backup") or {}
    if backup.get("status") in ("ok", "fail", "warn"):
        word = {"ok": "finished", "fail": "FAILED", "warn": "needs a look"}[backup["status"]]
        at = _hhmm(backup.get("at"), cfg)
        out.append(("Backup", word + (f" at {at}" if at else "")))
    storage = nas.get("storage") or {}
    if storage.get("used_pct") is not None:
        full = [f"{p['name']} is {round(p['used_pct'])}% full"
                for p in storage.get("pools") or [] if p.get("used_pct", 0) >= 90]
        out.append(("Storage", "; ".join([f"{round(storage['used_pct'])}% used", *full])))
    bad = [d["name"] for d in nas.get("disks") or [] if d.get("smart") in ("warn", "fail")]
    out.append(("Disks", f"SMART warnings on {', '.join(bad)}" if bad else "all healthy"))

    since = (now - UPDATES_SINCE).isoformat()
    updated = sorted({r["name"] for r in store.container_updates(100) if r["ts"] >= since})
    if updated:
        out.append(("Updated", ", ".join(updated)))
    for p in (store.get_cache("pinned") or {}).get("pins") or []:
        if p.get("behind"):
            out.append(("Pinned", f"{p['repo'].split('/')[-1]} at {p['current']}, "
                                  f"newest {p['latest']}"))
    return out


def markets(cfg: dict[str, Any], store: Store, now: datetime,
            notes: dict[str, str] | None = None) -> dict[str, Any]:
    """The Markets section (M29 step 3), from the hub's own portfolio data and
    never sent to Claude: the last session's move with amounts, the best and
    worst holding, the indices, why the big movers moved (`notes`, by ticker,
    step 4), and every holding for the folded table."""
    portfolio = store.get_cache("portfolio") or {}
    holdings = sorted(portfolio.get("holdings") or [],
                      key=lambda h: h.get("day_pct") or 0.0, reverse=True)
    if portfolio.get("total_value") is None:
        return {"markets": None, "market_lines": [], "holdings": []}
    change, pct = day_move(portfolio)
    total = (f"{report._money(portfolio['total_value'])}, "
             f"{report._money(change, signed=True)} ({report._pct(pct)})")
    as_of = datetime.fromisoformat(portfolio["as_of"]) if portfolio.get("as_of") else None
    if as_of and (portfolio.get("stale") or now - as_of > report.FRESH):
        total += f"; figures from {core.local(as_of, cfg):%a %H:%M}"
    lines: list[Item] = [("Portfolio", total)]

    def move(h: dict[str, Any]) -> str:
        return (f"{h['symbol']} {report._pct(h.get('day_pct') or 0.0)} "
                f"({report._money(h.get('day_abs') or 0.0, signed=True)})")

    if len(holdings) > 1:
        lines += [("Best", move(holdings[0])), ("Worst", move(holdings[-1]))]
    indices = (store.get_cache("indices") or {}).get("indices") or []
    if indices:
        lines.append(("Indices", ", ".join(f"{q['label']} {report._pct(q['day_pct'])}"
                                           for q in indices)))
    lines += list((notes or {}).items())
    return {
        "markets": "Markets · last session",
        "market_lines": [{"label": label, "text": text} for label, text in lines],
        "holdings": [{"symbol": h["symbol"], "pct": report._pct(h.get("day_pct") or 0.0),
                      "change": report._money(h.get("day_abs") or 0.0, signed=True)}
                     for h in holdings]}


def _sources(lead: str, others: list[dict[str, Any]]) -> str:
    if not others:
        return lead
    if len(others) == 1:
        return f"{lead} and {others[0]['source']}"
    return f"{lead} and {len(others)} more"


def news(store: Store, now: datetime) -> dict[str, Any]:
    """The News section (M29 step 5): the first stories the hub already shows on
    News and Home (grouped by Claude when that is on, else the newest per group),
    each linked, with its sources and Claude's sentence. No new AI call."""
    headlines = store.get_cache("headlines") or {}
    as_of = headlines.get("as_of")
    if not as_of or now - datetime.fromisoformat(as_of) > NEWS_FRESH:
        return {"news": None, "stories": []}
    picked = [h for h in headlines.get("items") or []
              if str(h.get("url", "")).startswith(("https://", "http://"))][:STORIES]
    return {
        "news": ("News · top stories" if headlines.get("grouped") else "News · latest")
        if picked else None,
        "stories": [{"url": h["url"], "title": h["title"],
                     "sources": _sources(h["source"], h.get("sources") or []),
                     "story": h.get("story")} for h in picked]}


def facts(cfg: dict[str, Any], store: Store, now: datetime) -> list[str]:
    """What Claude is told: the message's own items, with only the first event."""
    return [f"{label}: {text}"
            for label, text in your_day(cfg, store, now, full=False) + house(cfg, store, now)]


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
    answer = await ai.ask(cfg, store, feature=FEATURE, model=ai.BRIEFING_MODEL, system=SYSTEM,
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
        paragraph=str(data["opening"]).strip()[:OPENING_MAX])


# Held messages by severity, most serious first, as counted in the overnight line.
_COUNTED = (("error", "error", "errors"), ("warning", "warning", "warnings"),
            ("info", "info", "info"), ("ok", "OK", "OK"))


def overnight(held: list[dict[str, Any]], shown: frozenset[str] = frozenset()) -> dict[str, Any]:
    """The overnight section's values: a count by severity, and a line for each
    warning or error (the OK and info ones are only counted). One still open is
    already in House (`shown`, by title), so it is only counted here."""
    if not held:
        return {"overnight": None, "held": []}
    counts = []
    for severity, one, many in _COUNTED:
        n = sum(1 for m in held if m["severity"] == severity)
        if n:
            counts.append(f"{n} {one if n == 1 else many}")
    named = [m for m in held if m["severity"] in ("error", "warning") and m["title"] not in shown]
    title = "Overnight · " + ", ".join(counts)
    if len(named) > core.DIGEST_LIMIT:
        title += f" (the first {core.DIGEST_LIMIT} here, all on the Alerts page)"
    return {"overnight": title, "held": [
        {"level": core.LEVEL[m["severity"]], "title": m["title"]}
        for m in named[:core.DIGEST_LIMIT]]}


async def _notes(cfg: dict[str, Any], store: Store, now: datetime,
                 claude: ai.ClientFactory | None) -> dict[str, str]:
    portfolio = store.get_cache("portfolio") or {}
    if portfolio.get("total_value") is None:
        return {}
    return await market_notes.notes(cfg, store, portfolio, store.get_cache("indices"), now,
                                    claude)


async def run(cfg: dict[str, Any], store: Store, now: datetime | None = None,
              claude: ai.ClientFactory | None = None, telegram: Any = None) -> Briefing | None:
    """Make today's briefing, keep it for the panel and Home, and send it to Telegram.
    Nothing happens without an answer: yesterday's stays and is no longer shown.

    It takes over what quiet hours held for its chat (M29): those messages are
    counted in it and marked digested, so no "While you slept" repeats them at
    07:00. A template without {overnight} leaves them to that digest."""
    now = now or datetime.now(UTC)
    briefing = await make(cfg, store, now, claude)
    if briefing is None:
        return None
    store.put_cache(CACHE_KEY, briefing.model_dump(mode="json"))
    local = core.local(now, cfg)
    held: list[dict[str, Any]] = []
    if "{overnight}" in templates.text_of(store, "briefing"):
        held = core.held(store, core.routing(store).get("briefing", "nas"))
    the_house = house(cfg, store, now)
    sections = {name: [{"label": label, "text": text} for label, text in items]
                for name, items in (("your_day", your_day(cfg, store, now)),
                                    ("house", the_house))}
    shown = frozenset(text for _, text in the_house)
    sent = templates.message(store, "briefing", {
        "day": f"{local:%A}", "paragraph": briefing.paragraph} | sections
        | markets(cfg, store, now, await _notes(cfg, store, now, claude)) | news(store, now)
        | overnight(held, shown))
    # 06:30 is still quiet hours; the digest is wanted then, like the train.
    logged = await core.notify(store, cfg, source="briefing", category="briefing",
                               severity="info", title=sent.title, body=sent.body,
                               formatted=sent.html, bypass_quiet=True, now=now, telegram=telegram,
                               buttons=explain_open.buttons(cfg, store))
    if logged.status == "sent" and held:
        core.mark_digested(store, [m["id"] for m in held], now)
    return briefing
