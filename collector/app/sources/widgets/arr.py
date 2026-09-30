"""Arr widgets: Sonarr, Radarr, Bazarr, Prowlarr.

Only cheap endpoints: queue/status and a one-row page of wanted/missing give
totals without downloading the library. Checked against each project's source
(2026-09): Sonarr main and Radarr master share the v3 routes; Bazarr's
/api/badges; Prowlarr's /api/v1/indexer and /api/v1/indexerstats.
"""

from __future__ import annotations

import httpx

from ...models import Stat
from .http import expect, get


async def _queue_and_missing(
    client: httpx.AsyncClient, base_url: str, key: str
) -> tuple[int, int]:
    headers = {"X-Api-Key": key}
    queue = expect(await get(client, f"{base_url}/api/v3/queue/status", headers), dict)
    missing = expect(
        await get(client, f"{base_url}/api/v3/wanted/missing", headers, pageSize=1), dict
    )
    return queue["totalCount"], missing["totalRecords"]


async def sonarr(client: httpx.AsyncClient, base_url: str, key: str) -> list[Stat]:
    queued, missing = await _queue_and_missing(client, base_url, key)
    return [Stat(label="Queued", value=queued), Stat(label="Missing", value=missing)]


async def radarr(client: httpx.AsyncClient, base_url: str, key: str) -> list[Stat]:
    queued, missing = await _queue_and_missing(client, base_url, key)
    return [Stat(label="Queued", value=queued), Stat(label="Missing", value=missing)]


async def bazarr(client: httpx.AsyncClient, base_url: str, key: str) -> list[Stat]:
    badges = expect(await get(client, f"{base_url}/api/badges", {"X-API-KEY": key}), dict)
    # Counts of episodes and movies still missing subtitles.
    return [
        Stat(label="Episodes missing", value=badges["episodes"]),
        Stat(label="Movies missing", value=badges["movies"]),
    ]


async def prowlarr(client: httpx.AsyncClient, base_url: str, key: str) -> list[Stat]:
    headers = {"X-Api-Key": key}
    indexers = expect(await get(client, f"{base_url}/api/v1/indexer", headers), list)
    stats = expect(await get(client, f"{base_url}/api/v1/indexerstats", headers), dict)
    per_indexer = expect(stats.get("indexers", []), list)
    return [
        Stat(label="Indexers", value=sum(1 for i in indexers if i.get("enable"))),
        Stat(label="Grabs", value=sum(i.get("numberOfGrabs", 0) for i in per_indexer)),
        Stat(label="Queries", value=sum(i.get("numberOfQueries", 0) for i in per_indexer)),
    ]
