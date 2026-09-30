"""Monitoring widgets: Uptime Kuma and Scrutiny. Neither needs a key.

- Uptime Kuma 2.x: the public status page API. /api/status-page/heartbeat/<slug>
  lists each monitor's recent heartbeats oldest first, plus a 24-hour uptime
  fraction per monitor ("<id>_24"). Checked against its source (2026-09).
- Scrutiny: /api/summary, parsed like the NAS view does.
"""

from __future__ import annotations

import httpx

from ...models import Stat
from ..nas import parse_scrutiny
from .http import expect, get

# Uptime Kuma heartbeat status codes (src/util.ts).
DOWN, UP, PENDING, MAINTENANCE = 0, 1, 2, 3


async def uptimekuma(
    client: httpx.AsyncClient, base_url: str, key: str, slug: str = "nas"
) -> list[Stat]:
    body = expect(await get(client, f"{base_url}/api/status-page/heartbeat/{slug}", {}), dict)
    beats = expect(body.get("heartbeatList"), dict)
    latest = [expect(b, list)[-1].get("status") for b in beats.values() if b]
    uptimes = [v for k, v in expect(body.get("uptimeList", {}), dict).items() if k.endswith("_24")]

    stats = [
        Stat(label="Up", value=sum(1 for s in latest if s == UP)),
        Stat(label="Down", value=sum(1 for s in latest if s == DOWN)),
    ]
    if uptimes:
        stats.append(
            Stat(label="Uptime 24h", value=round(sum(uptimes) / len(uptimes) * 100, 2),
                 unit="percent")
        )
    return stats


async def scrutiny(client: httpx.AsyncClient, base_url: str, key: str) -> list[Stat]:
    body = expect(await get(client, f"{base_url}/api/summary", {}), dict)
    summary = expect(expect(body.get("data"), dict).get("summary"), dict)
    disks = parse_scrutiny(summary)
    return [
        Stat(label="Disks", value=len(disks)),
        Stat(label="Failed", value=sum(1 for d in disks if d.smart == "fail")),
        Stat(label="Warnings", value=sum(1 for d in disks if d.smart == "warn")),
    ]
