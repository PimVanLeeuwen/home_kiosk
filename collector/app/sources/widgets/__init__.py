"""Live stats for service tiles: one adapter per app, like homepage's widgets.

Adapters reach each app on the NAS through `widgets.host` and the service's
port, with the app's API key from the hub's .env. One app failing never fails
the others: its error is recorded next to its (absent) stats.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any

import httpx

from ...models import Service, Stat, WidgetResult, WidgetStats
from ...store import Store
from . import arr, downloads, media, monitoring

log = logging.getLogger(__name__)

# widget type -> (adapter, needs an API key)
REGISTRY: dict[str, tuple[Callable[..., Awaitable[list[Stat]]], bool]] = {
    "jellyfin": (media.jellyfin, True),
    "immich": (media.immich, True),
    "jellyseerr": (media.jellyseerr, True),
    "sonarr": (arr.sonarr, True),
    "radarr": (arr.radarr, True),
    "bazarr": (arr.bazarr, True),
    "prowlarr": (arr.prowlarr, True),
    "sabnzbd": (downloads.sabnzbd, True),
    # No RPC auth on this Transmission (it sits behind gluetun, LAN only).
    "transmission": (downloads.transmission, False),
    "uptimekuma": (monitoring.uptimekuma, False),
    "scrutiny": (monitoring.scrutiny, False),
}

TIMEOUT_SECONDS = 8


class WidgetError(Exception):
    """A failure with a message fit for the tile."""


def describe(exc: Exception) -> str:
    """A short reason without URLs, headers or keys."""
    if isinstance(exc, WidgetError):
        return str(exc)
    if isinstance(exc, httpx.HTTPStatusError):
        code = exc.response.status_code
        if code in (401, 403):
            return f"API key refused ({code})"
        return f"HTTP {code}"
    if isinstance(exc, httpx.TimeoutException):
        return "Timed out"
    if isinstance(exc, httpx.ConnectError):
        return "Not reachable"
    return "Unexpected response"


async def _one(
    client: httpx.AsyncClient,
    service: Service,
    host: str,
    keys: dict[str, str],
    options: dict[str, dict[str, Any]],
) -> WidgetResult:
    adapter, needs_key = REGISTRY[service.widget or ""]
    key = (keys.get(service.widget or "") or "").strip()
    if needs_key and not key:
        env = f"{(service.widget or '').upper()}_API_KEY"
        return WidgetResult(error=f"No API key set ({env})")
    base_url = f"http://{host}:{service.port}"
    try:
        extra = options.get(service.widget or "") or {}
        return WidgetResult(stats=await adapter(client, base_url, key, **extra))
    except Exception as exc:
        # Log the class (and an HTTP status) only: some exceptions carry the
        # request, and the request carries the key.
        status = f" {exc.response.status_code}" if isinstance(exc, httpx.HTTPStatusError) else ""
        log.warning("widget %s for %s failed: %s%s", service.widget, service.id,
                    type(exc).__name__, status)
        return WidgetResult(error=describe(exc))


async def collect(
    cfg: dict[str, Any], store: Store, transport: httpx.AsyncBaseTransport | None = None
) -> WidgetStats:
    """`transport` is for tests (httpx.MockTransport)."""
    widget_cfg = cfg.get("widgets") or {}
    host = widget_cfg.get("host", "localhost")
    keys = widget_cfg.get("keys") or {}
    options = widget_cfg.get("options") or {}
    # Links have no port, so no widget either.
    services = [s for s in store.list_services() if s.widget in REGISTRY and s.port]

    async with httpx.AsyncClient(
        timeout=TIMEOUT_SECONDS, follow_redirects=True, transport=transport
    ) as client:
        results = await asyncio.gather(*(_one(client, s, host, keys, options) for s in services))

    return WidgetStats(
        as_of=datetime.now(UTC),
        stale=False,
        items={s.id: r for s, r in zip(services, results, strict=True)},
    )
