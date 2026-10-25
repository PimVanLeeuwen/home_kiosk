"""Documents widget: Paperless-ngx.

Endpoint and fields checked against Paperless's source (2026-10, v3.3):
/api/statistics/ with token auth (`Authorization: Token <key>`), the key from
the owner's profile in Paperless. `documents_inbox` is null when no tag is
marked as an inbox tag; the tile then leaves the inbox out.
"""

from __future__ import annotations

import httpx

from ...models import Stat
from .http import expect as _expect
from .http import get as _get


async def paperless(client: httpx.AsyncClient, base_url: str, key: str) -> list[Stat]:
    stats = _expect(
        await _get(client, f"{base_url}/api/statistics/", {"Authorization": f"Token {key}"}), dict
    )
    tiles = [Stat(label="Documents", value=stats["documents_total"])]
    if stats.get("documents_inbox") is not None:
        tiles.append(Stat(label="Inbox", value=stats["documents_inbox"]))
    tiles.append(Stat(label="Correspondents", value=stats["correspondent_count"]))
    return tiles
