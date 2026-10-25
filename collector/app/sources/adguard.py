"""DNS blocking on Home (plan.md M24): AdGuard Home's last 24 hours.

Read-only: `/control/stats` (totals, hourly buckets, the most-blocked domains)
and `/control/status` (is blocking on), as AdGuard's own "hub" user (AdGuard has
no read-only users). Fields checked against a running v0.107.79 (2026-10).

Only totals and domains leave AdGuard: which device asks for what is browsing
history, so `top_clients` is never read. When AdGuard stops answering, the last
counts stay with `answering: false` once it has failed for GRACE (a restart by
Watchtower stays quiet); the house then resolves through Quad9, unfiltered.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx

from ..models import DnsHour, DnsStats
from ..store import Store
from .widgets.dns import basic_auth

log = logging.getLogger(__name__)

CACHE_KEY = "dns"
TIMEOUT_SECONDS = 8
GRACE = timedelta(minutes=3)


def settings(cfg: dict[str, Any]) -> dict[str, Any]:
    a = cfg.get("adguard") or {}
    url = str(a.get("url") or "").strip().rstrip("/")
    password = str(a.get("password") or "").strip()
    return {"url": url, "user": str(a.get("user") or "hub"), "password": password,
            "enabled": bool(url and password)}


def _top(stats: dict[str, Any]) -> tuple[str | None, int | None]:
    """AdGuard lists the top domains as one-key objects, most first."""
    for entry in stats.get("top_blocked_domains") or []:
        if isinstance(entry, dict) and entry:
            domain, count = next(iter(entry.items()))
            return str(domain), int(count)
    return None, None


def parse(stats: dict[str, Any], status: dict[str, Any], now: datetime) -> DnsStats:
    queries = int(stats["num_dns_queries"])
    blocked = int(stats["num_blocked_filtering"])
    pairs = zip(stats.get("dns_queries") or [], stats.get("blocked_filtering") or [], strict=False)
    hours = [DnsHour(queries=int(q), blocked=int(b)) for q, b in pairs]
    domain, count = _top(stats)
    return DnsStats(
        as_of=now, protection=bool(status.get("protection_enabled", True)),
        queries=queries, blocked=blocked,
        share=round(blocked / queries * 100, 1) if queries else None,
        hours=hours, top_blocked=domain, top_blocked_count=count,
    )


def _not_answering(exc: Exception) -> bool:
    """Down, not misconfigured: a refused password still raises (and logs) as itself."""
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code >= 500
    return isinstance(exc, httpx.TransportError)


async def collect(cfg: dict[str, Any], store: Store,
                  transport: httpx.AsyncBaseTransport | None = None,
                  now: datetime | None = None) -> DnsStats:
    """`transport` and `now` are for tests."""
    s = settings(cfg)
    now = now or datetime.now(UTC)
    auth = basic_auth(s["user"], s["password"])
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS, transport=transport) as client:
            stats = await client.get(f"{s['url']}/control/stats", headers=auth)
            stats.raise_for_status()
            status = await client.get(f"{s['url']}/control/status", headers=auth)
            status.raise_for_status()
        return parse(stats.json(), status.json(), now)
    except Exception as exc:
        previous = store.get_cache(CACHE_KEY)
        if not _not_answering(exc) or previous is None:
            raise
        log.warning("AdGuard is not answering: %s", type(exc).__name__)
        since = datetime.fromisoformat(previous.get("failing_since") or now.isoformat())
        return DnsStats.model_validate(previous | {
            "stale": True, "failing_since": since,
            "answering": now - since < GRACE,
        })
