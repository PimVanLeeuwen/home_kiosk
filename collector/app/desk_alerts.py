"""The desk panels' alerts (plan.md M16, M20): the House panel's Alerts screen and the
ERROR takeover. Read from the hub's open incidents (alerts/rules.py); only warnings
and errors count, as info messages need nobody.

The Alerts screen shows the worst open alert large, with the others below; when none
is open, All quiet with how long nothing has needed you and this week's days. An open
error also takes over all three panels until it is dismissed on one of them
(decided 2026-10-22: once for all panels, until the incident resolves; also in quiet
hours). Ready to draw.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from .alerts import rules
from .panel_text import latin1
from .store import Store

RANK = {"error": 0, "warning": 1}
MAX_OTHERS = 3
MAX_BODY = 200
DAY_LETTERS = "MTWTFSS"


def _shown(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Warnings and errors, the worst first, then the newest."""
    kept = [r for r in rows if r["severity"] in RANK]
    kept.sort(key=lambda r: r["opened_at"], reverse=True)
    kept.sort(key=lambda r: RANK[r["severity"]])
    return kept


def _body(text: str) -> str:
    """The first lines of a message as one, for a panel: no tables, no line breaks."""
    line = latin1(" ".join(text.split()))
    return line if len(line) <= MAX_BODY else line[:MAX_BODY - 3].rstrip() + "..."


def _since(at: str, zone: ZoneInfo, now: datetime) -> str:
    """"09:12" today, "Tue 09:12" this week, "12 Oct" before."""
    when = datetime.fromisoformat(at).astimezone(zone)
    local = now.astimezone(zone)
    if when.date() == local.date():
        return when.strftime("%H:%M")
    if local.date() - when.date() < timedelta(days=7):
        return when.strftime("%a %H:%M")
    return f"{when.day} {when.strftime('%b')}"


def _span(since: str, now: datetime) -> str:
    """"20 min", "5 hours", "2 days"."""
    minutes = max(0, int((now - datetime.fromisoformat(since)).total_seconds() // 60))
    if minutes < 60:
        return f"{minutes} min"
    if minutes < 48 * 60:
        hours = minutes // 60
        return f"{hours} hour{'s' if hours != 1 else ''}"
    return f"{minutes // (24 * 60)} days"


def _week(store: Store, zone: ZoneInfo, now: datetime) -> list[dict[str, Any]]:
    """This week, Monday first: each day with the worst alert opened on it."""
    today = now.astimezone(zone).date()
    monday = today - timedelta(days=today.weekday())
    worst: dict[int, str] = {}
    for row in rules.incidents(store, limit=200):
        if row["severity"] not in RANK:
            continue
        day = (datetime.fromisoformat(row["opened_at"]).astimezone(zone).date() - monday).days
        if 0 <= day < 7 and RANK[row["severity"]] < RANK.get(worst.get(day, ""), 9):
            worst[day] = row["severity"]
    return [{"letter": DAY_LETTERS[d], "alert": worst.get(d, ""), "today": d == today.weekday(),
             "future": d > today.weekday()} for d in range(7)]


def _quiet_line(store: Store, now: datetime) -> str:
    ended = [r["resolved_at"] for r in rules.incidents(store, limit=200)
             if r["severity"] in RANK and r["resolved_at"]]
    if not ended:
        return "Nothing has needed you lately"
    return f"Nothing has needed you for {_span(max(ended), now)}"


def alerts_screen(store: Store, zone: ZoneInfo, now: datetime) -> dict[str, Any]:
    shown = _shown(list(rules.open_incidents(store).values()))
    base = {"kind": "alerts", "stale": False, "present": True, "title": "ALERTS",
            "status": f"{len(shown)} OPEN" if shown else "NONE OPEN",
            "tone": shown[0]["severity"] if shown else "ok"}
    if not shown:
        return base | {"quiet": {"line": _quiet_line(store, now),
                                 "days": _week(store, zone, now)}}
    top = shown[0]
    return base | {
        "hero": {"severity": top["severity"].upper(), "title": latin1(top["title"]),
                 "body": _body(top["body"]),
                 "line": f"Open {_span(top['opened_at'], now)} · since "
                         f"{_since(top['opened_at'], zone, now)}"},
        "others": [{"severity": r["severity"], "title": latin1(r["title"])}
                   for r in shown[1:1 + MAX_OTHERS]],
    }


def takeover(store: Store, zone: ZoneInfo, now: datetime) -> dict[str, Any] | None:
    """The newest open error nobody dismissed yet, for all three panels; else None."""
    errors = [r for r in rules.open_incidents(store).values()
              if r["severity"] == "error" and not r.get("dismissed_at")]
    if not errors:
        return None
    top = max(errors, key=lambda r: r["opened_at"])
    return {"key": top["key"], "title": latin1(top["title"]), "body": _body(top["body"]),
            "since": _since(top["opened_at"], zone, now)}


def dismiss(store: Store, key: str, now: datetime) -> bool:
    """Dismisses an open incident's takeover on every panel; False when none is open."""
    with store.connect() as conn:
        done = conn.execute(
            "UPDATE alert_incident SET dismissed_at = ? WHERE key = ? AND resolved_at IS NULL",
            (now.isoformat(), key))
        return done.rowcount > 0
