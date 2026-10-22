"""The House panel's NAS screen (plan.md M20, the instrument design of 2026-10-10): a
gauge for the fullest pool with a mark where it would alert, its size and runway, then
CPU and memory with their last 24 hours as sparklines, and the disks with the UPS.
Ready to draw, from `/api/nas`, its history and `/api/ups`; the pill counts the open
alerts about the NAS itself, so the panel and Telegram agree.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from .alerts import rules
from .sources import nas as nas_source
from .sources import ups as ups_source
from .store import Store

RULES = ("disk_space", "smart", "container_health")
POINTS = 24  # per sparkline: the day in hours
UPS_WORDS = {"online": "UPS ok", "on_battery": "UPS on battery", "low_battery": "UPS battery low"}


def tb(n: float) -> str:
    """Sizes as the NAS page shows them: "15.8 TB", "912 GB"."""
    return f"{n / 1e12:.1f} TB" if n >= 1e12 else f"{n / 1e9:.0f} GB"


def runway(months: float | None) -> str:
    if months is None:
        return ""
    if months < 1:
        return "full within a month"
    if months < 24:
        return f"full in about {round(months)} month{'s' if round(months) != 1 else ''}"
    return f"full in about {round(months / 12)} years"


def spark(values: list[float | None]) -> list[int]:
    """At most POINTS whole percentages, each the average of its share of the day."""
    kept = [v for v in values if v is not None]
    if not kept:
        return []
    size = max(1, -(-len(kept) // POINTS))
    return [round(sum(part) / len(part)) for part in
            (kept[i:i + size] for i in range(0, len(kept), size))]


def _open_problems(store: Store, names: tuple[str, ...]) -> int:
    return sum(1 for r in rules.open_incidents(store).values() if r["rule"] in names
               and r["severity"] in ("warning", "error"))


def nas_screen(store: Store, zone: ZoneInfo, now: datetime) -> dict[str, Any]:
    nas = store.get_cache("nas")
    pools = (nas or {}).get("storage", {}).get("pools") or []
    if not nas or not pools:
        return {"kind": "nas", "stale": False, "present": False}
    fullest = max(pools, key=lambda p: p["used_pct"])
    limit = rules.rule_settings(store)["disk_space"]["threshold_pct"]
    history = nas_source.history(store.recent_nas_samples(now - timedelta(hours=24)))
    points = [p.model_dump() if hasattr(p, "model_dump") else p for p in history]
    disks = nas.get("disks") or []
    ups = store.get_cache(ups_source.CACHE_KEY) or {}
    problems = _open_problems(store, RULES)
    return {
        "kind": "nas",
        "stale": bool(nas.get("stale")),
        "present": True,
        "title": "NAS · STORAGE",
        "status": f"{problems} ISSUE{'S' if problems != 1 else ''}" if problems else "HEALTHY",
        "warn": problems > 0,
        "pool": fullest["name"],
        "used_pct": round(fullest["used_pct"]),
        "limit_pct": int(limit),
        "size": f"{fullest['name']} · {tb(fullest['used_bytes'])} of {tb(fullest['total_bytes'])}",
        "runway": runway(fullest.get("projection_months")),
        "cpu": round(nas.get("cpu_pct") or 0),
        "cpu_points": spark([p.get("cpu") for p in points]),
        "ram": round(nas.get("ram_pct") or 0),
        "ram_points": spark([p.get("ram") for p in points]),
        "disks": [d.get("smart") == "ok" for d in disks][:8],
        "disks_line": f"{sum(d.get('smart') == 'ok' for d in disks)} of {len(disks)}",
        "ups": UPS_WORDS.get(ups.get("status") or "", ""),
        "ups_ok": ups.get("status") in (None, "online"),
    }
