"""The House panel's My sites screen (plan.md M20, tiles as chosen on 2026-10-21): a
tile per site with its name as Kuma has it, its response time (or how long it has been
down), the 30-day uptime below 100% and its 30 days as a strip. Ready to draw, from
the Services page's `sites` data (sources/my_sites.py).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from .sources import my_sites
from .store import Store

MAX_SITES = 8  # four rows of two tiles
DAY_LETTERS = {"up": "u", "blip": "b", "down": "d"}  # anything else: "n", no record


def _down_for(since: str | None, now: datetime) -> str:
    """"down 4 min", "down 2 h", "down 3 d"; plain "down" without a start."""
    if not since:
        return "down"
    minutes = max(0, int((now - datetime.fromisoformat(since)).total_seconds() // 60))
    if minutes < 60:
        return f"down {minutes} min"
    if minutes < 48 * 60:
        return f"down {minutes // 60} h"
    return f"down {minutes // (24 * 60)} d"


def _tile(site: dict[str, Any], now: datetime) -> dict[str, Any]:
    days = "".join(DAY_LETTERS.get(d, "n") for d in site.get("days") or [])
    up = site.get("up")
    pct = site.get("uptime_pct")
    ping = site.get("ping_ms")
    return {
        "name": site.get("name") or "?",
        "state": "down" if up is False else "up" if up else "unknown",
        "left": _down_for(site.get("down_since"), now) if up is False
        else f"{ping} ms" if ping is not None else "",
        "right": f"{pct:g}%" if pct is not None and pct < 100 else "",
        # The tile's dot: its worst day this month.
        "worst": "down" if "d" in days else "blip" if "b" in days else "up",
        "days": days,
    }


def sites_screen(store: Store, zone: ZoneInfo, now: datetime) -> dict[str, Any]:
    data = store.get_cache(my_sites.CACHE_KEY) or {}
    sites = (data.get("sites") or [])[:MAX_SITES]
    if not sites:
        return {"kind": "sites", "stale": False, "present": False}
    tiles = [_tile(site, now) for site in sites]
    down = sum(t["state"] == "down" for t in tiles)
    return {
        "kind": "sites",
        "stale": bool(data.get("stale")),
        "present": True,
        "title": "MY SITES · 30 DAYS",
        "status": f"{down} DOWN" if down else "ALL UP",
        "down": down,
        "sites": tiles,
    }
