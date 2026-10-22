"""The House panel's Services screen (plan.md M20, the ring as planned, confirmed on
2026-10-22): the outside services the house uses, as logos in a ring around a check
while all is well; during an incident a card with the service, how long it has run
and its last steps, and the others below. Only turns with House, no takeover.
Ready to draw, from `/api/outside-services` (sources/outside_services.py).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from .sources import outside_services
from .store import Store

MAX_SERVICES = 8
MAX_STEPS = 3
# The worst first; "unknown" (a page that could not be read) is no incident.
RANK = {"outage": 0, "degraded": 1, "maintenance": 2}
WORDS = {"outage": "Outage", "degraded": "Degraded", "maintenance": "Maintenance"}


def _for(since: str | None, now: datetime) -> str:
    """"for 24 min", "for 3 h", "for 2 d"; "" without a start."""
    if not since:
        return ""
    minutes = max(0, int((now - datetime.fromisoformat(since)).total_seconds() // 60))
    if minutes < 60:
        return f"for {minutes} min"
    if minutes < 48 * 60:
        return f"for {minutes // 60} h"
    return f"for {minutes // (24 * 60)} d"


def _incident(service: dict[str, Any], zone: ZoneInfo, now: datetime) -> dict[str, Any]:
    """The service's worst incident (the oldest of those): what, how long, its last steps."""
    state = service["state"]
    incidents = sorted(service.get("incidents") or [],
                       key=lambda i: (RANK.get(i.get("impact"), 9), i.get("started_at") or ""))
    first = incidents[0] if incidents else {}
    steps = [{"status": (u.get("status") or "").replace("_", " ").capitalize(),
              "time": datetime.fromisoformat(u["at"]).astimezone(zone).strftime("%H:%M")}
             for u in reversed(first.get("updates") or []) if u.get("at")][:MAX_STEPS]
    line = " · ".join(x for x in (WORDS[state], _for(first.get("started_at"), now)) if x)
    return {"key": service["key"], "name": service["name"], "state": state, "line": line,
            "title": first.get("title") or "", "steps": steps}


def services_screen(store: Store, zone: ZoneInfo, now: datetime) -> dict[str, Any]:
    data = store.get_cache(outside_services.CACHE_KEY) or {}
    services = (data.get("services") or [])[:MAX_SERVICES]
    if not services:
        return {"kind": "services", "stale": False, "present": False}
    troubled = sorted((s for s in services if s.get("state") in RANK),
                      key=lambda s: RANK[s["state"]])
    if not troubled:
        status = "ALL OPERATIONAL"
    elif all(s["state"] == "maintenance" for s in troubled):
        status = "MAINTENANCE"
    else:
        status = f"{len(troubled)} INCIDENT{'S' if len(troubled) > 1 else ''}"
    more = len(troubled) - 1
    others = ("" if not troubled
              else f"the other {len(services) - 1} are operational" if not more
              else f"{more} more not fully operational")
    return {
        "kind": "services",
        "stale": bool(data.get("stale")),
        "present": True,
        "title": "SERVICES",
        "status": status,
        "tone": troubled[0]["state"] if troubled else "ok",
        "services": [{"key": s.get("key") or "", "name": s.get("name") or "?",
                      "state": s.get("state") or "unknown"} for s in services],
        "incident": _incident(troubled[0], zone, now) if troubled else None,
        "others": others,
    }
