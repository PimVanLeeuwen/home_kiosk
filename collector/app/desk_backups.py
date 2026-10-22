"""The House panel's Backups screen (plan.md M20, the design of 2026-10-10): a seal with
last night's start, how long it took and how much it copied, and the last restore
check; the NAS to Hetzner (encrypted) line with its Storage Box; and the last 30 nights
as bars by how long each took (decided 2026-10-22), a slow night amber, a failed one
red. Ready to draw, from `/api/backups` and the restore checks in `/api/database-dumps`;
the pill counts the open alerts about backups, so the panel and Telegram agree.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from statistics import median
from typing import Any
from zoneinfo import ZoneInfo

from .alerts import rules
from .desk_nas import tb
from .sources import dumps
from .store import Store

RULES = ("backup_missing", "storage_box")
NIGHTS = 30
SLOW = 1.5  # times the usual length


def _seconds(run: dict[str, Any]) -> int:
    return max(0, int((datetime.fromisoformat(run["finished"])
                       - datetime.fromisoformat(run["started"])).total_seconds()))


def _took(seconds: int) -> str:
    """"1 h 12 min", "47 min", "40 s"."""
    if seconds < 60:
        return f"{seconds} s"
    hours, minutes = divmod(seconds // 60, 60)
    return f"{hours} h {minutes} min" if hours else f"{minutes} min"


def _when(started: datetime, now: datetime) -> str:
    """"Today" (after 06:00), "Last night" (from 18:00 the day before), "Yesterday", "21 Oct"."""
    today = now.date()
    if started.date() == today:
        return "Today" if started.hour >= 6 else "Last night"
    if started.date() == today - timedelta(days=1):
        return "Last night" if started.hour >= 18 else "Yesterday"
    return f"{started.day} {started.strftime('%b')}"


def _nights(runs: list[dict[str, Any]], zone: ZoneInfo) -> list[dict[str, Any]]:
    """One per night, oldest first: the night's last run, failed when any run failed."""
    by_day: dict[str, list[dict[str, Any]]] = {}
    for run in runs:
        day = datetime.fromisoformat(run["started"]).astimezone(zone).date().isoformat()
        by_day.setdefault(day, []).append(run)
    nights = []
    for day in sorted(by_day)[-NIGHTS:]:
        last = max(by_day[day], key=lambda r: r["started"])
        nights.append({"seconds": _seconds(last), "ok": all(r["ok"] for r in by_day[day])})
    usual = median([n["seconds"] for n in nights if n["ok"]] or [0])
    for n in nights:
        n["state"] = "failed" if not n["ok"] else "slow" if usual and n["seconds"] > SLOW * usual \
            else "ok"
    return nights


def _restore(store: Store, zone: ZoneInfo, now: datetime) -> tuple[str, str]:
    """The last restore check in words, and its tone: "ok", "failed" or "none"."""
    checks = (store.get_cache(dumps.CACHE_KEY) or {}).get("restore_checks") or []
    if not checks:
        return "No restore check yet", "none"
    last = max(checks, key=lambda c: c["finished"])
    when = datetime.fromisoformat(last["finished"]).astimezone(zone)
    if not last["ok"]:
        return f"Restore check failed on {when.day} {when.strftime('%b')}", "failed"
    days = (now.astimezone(zone).date() - when.date()).days
    ago = "today" if days == 0 else "yesterday" if days == 1 else f"{days} days ago"
    return f"Restore verified {ago}", "ok"


def backups_screen(store: Store, zone: ZoneInfo, now: datetime) -> dict[str, Any]:
    data = store.get_cache("backups")
    runs = (data or {}).get("runs") or []
    if not runs:
        return {"kind": "backups", "stale": False, "present": False}
    last = max(runs, key=lambda r: r["started"])
    started = datetime.fromisoformat(last["started"]).astimezone(zone)
    copied = sum(v.get("bytes") or 0 for v in last.get("volumes") or [])
    problems = sum(1 for r in rules.open_incidents(store).values()
                   if r["rule"] in RULES and r["severity"] in ("warning", "error"))
    restore, restore_tone = _restore(store, zone, now)
    box = data.get("storage_box") or {}
    nights = _nights(runs, zone)
    return {
        "kind": "backups",
        "stale": bool(data.get("stale")),
        "present": True,
        "title": "BACKUPS",
        "status": f"{problems} PROBLEM{'S' if problems != 1 else ''}" if problems else "ALL SAFE",
        "warn": problems > 0,
        "ok": bool(last["ok"]),
        "time": started.strftime("%H:%M"),
        "line": " · ".join(p for p in (
            _when(started, now.astimezone(zone)),
            _took(_seconds(last)), tb(copied) if copied >= 1e9 else f"{copied / 1e6:.0f} MB") if p),
        "restore": restore,
        "restore_tone": restore_tone,
        "box": f"Storage Box · {round(box['used_pct'])}% used" if box.get("used_pct") is not None
        else "",
        "nights": [{"minutes": round(n["seconds"] / 60), "state": n["state"]} for n in nights],
    }
