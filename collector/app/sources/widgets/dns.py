"""DNS widget: AdGuard Home.

Endpoint and fields checked against a running AdGuard v0.107.79 (2026-10):
/control/stats with basic auth. AdGuard has no read-only users, so the hub has
a user of its own ("hub" by default) whose password is the widget's key. The
counts cover the last 24 hours (the stats interval in AdGuardHome.yaml). Only
totals: which device asks for what is browsing history (plan.md M24).
"""

from __future__ import annotations

import base64

import httpx

from ...models import Stat
from .http import expect as _expect
from .http import get as _get


def basic_auth(user: str, password: str) -> dict[str, str]:
    token = base64.b64encode(f"{user}:{password}".encode()).decode()
    return {"Authorization": f"Basic {token}"}


async def adguard(
    client: httpx.AsyncClient, base_url: str, key: str, user: str = "hub"
) -> list[Stat]:
    stats = _expect(await _get(client, f"{base_url}/control/stats", basic_auth(user, key)), dict)
    queries = int(stats["num_dns_queries"])
    blocked = int(stats["num_blocked_filtering"])
    tiles = [Stat(label="Queries 24h", value=queries), Stat(label="Blocked", value=blocked)]
    if queries:
        share = round(blocked / queries * 100, 1)
        tiles.append(Stat(label="Share blocked", value=share, unit="percent"))
    return tiles
