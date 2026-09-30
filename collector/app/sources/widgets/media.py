"""Media widgets: Jellyfin, Immich, Jellyseerr.

Endpoints and fields checked against each project's source (2026-09):
- Jellyfin: /Sessions and /Items/Counts. The legacy X-Emby-Token header only
  works with EnableLegacyAuthorization, so the MediaBrowser Authorization
  header is used.
- Immich: /api/server/statistics (admin key with the server.statistics permission).
- Jellyseerr: /api/v1/request/count.
"""

from __future__ import annotations

import httpx

from ...models import Stat
from .http import expect as _expect
from .http import get as _get


async def jellyfin(client: httpx.AsyncClient, base_url: str, key: str) -> list[Stat]:
    headers = {"Authorization": f'MediaBrowser Token="{key}"'}
    sessions = _expect(
        await _get(client, f"{base_url}/Sessions", headers, activeWithinSeconds=600), list
    )
    counts = _expect(await _get(client, f"{base_url}/Items/Counts", headers), dict)
    streaming = sum(1 for s in sessions if isinstance(s, dict) and s.get("NowPlayingItem"))
    return [
        Stat(label="Streaming", value=streaming),
        Stat(label="Movies", value=counts.get("MovieCount", 0)),
        Stat(label="Series", value=counts.get("SeriesCount", 0)),
    ]


async def immich(client: httpx.AsyncClient, base_url: str, key: str) -> list[Stat]:
    stats = _expect(
        await _get(client, f"{base_url}/api/server/statistics", {"x-api-key": key}), dict
    )
    return [
        Stat(label="Photos", value=stats["photos"]),
        Stat(label="Videos", value=stats["videos"]),
        Stat(label="Storage", value=stats["usage"], unit="bytes"),
    ]


async def jellyseerr(client: httpx.AsyncClient, base_url: str, key: str) -> list[Stat]:
    counts = _expect(
        await _get(client, f"{base_url}/api/v1/request/count", {"X-Api-Key": key}), dict
    )
    return [
        Stat(label="Pending", value=counts["pending"]),
        Stat(label="Processing", value=counts["processing"]),
        Stat(label="Available", value=counts["available"]),
    ]
