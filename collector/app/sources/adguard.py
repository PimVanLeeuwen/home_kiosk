"""DNS blocking on Home (plan.md M24): AdGuard Home's last 24 hours.

Read-only: `/control/stats` (totals, hourly buckets, the most-blocked domains)
and `/control/status` (is blocking on), as AdGuard's own "hub" user (AdGuard has
no read-only users). Fields checked against a running v0.107.79 (2026-10).

Only totals and domains leave AdGuard: which device asks for what is browsing
history, so `top_clients` is never read.

With `dns` set (the NAS's LAN address, where AdGuard serves DNS), every round
also sends one real lookup there: the admin page can answer while DNS does not.
Any answer counts, a SERVFAIL too (then AdGuard runs, its upstream does not).
When DNS fails (or, without `dns`, the admin page), `failing` says which, and
`answering` turns false once it has failed for GRACE (a restart by Watchtower
stays quiet); the last counts stay. The house then resolves through Quad9,
unfiltered; the `adguard` alert rule reports it.
"""

from __future__ import annotations

import asyncio
import logging
import secrets
import struct
from collections.abc import Awaitable, Callable
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
PROBE_NAME = "example.com"
PROBE_TIMEOUT_SECONDS = 3

Probe = Callable[[str], Awaitable[bool]]


def settings(cfg: dict[str, Any]) -> dict[str, Any]:
    a = cfg.get("adguard") or {}
    url = str(a.get("url") or "").strip().rstrip("/")
    password = str(a.get("password") or "").strip()
    return {"url": url, "user": str(a.get("user") or "hub"), "password": password,
            "dns": str(a.get("dns") or "").strip(), "enabled": bool(url and password)}


def query(name: str, ident: int) -> bytes:
    """A DNS query for the name's A record, recursion desired."""
    labels = b"".join(bytes([len(p)]) + p.encode() for p in name.split(".")) + b"\0"
    return struct.pack(">HHHHHH", ident, 0x0100, 1, 0, 0, 0) + labels + struct.pack(">HH", 1, 1)


def is_answer(packet: bytes, ident: int) -> bool:
    """A response to our query, whatever its result code."""
    if len(packet) < 12:
        return False
    got, flags = struct.unpack(">HH", packet[:4])
    return got == ident and bool(flags & 0x8000)


class _Lookup(asyncio.DatagramProtocol):
    def __init__(self, ident: int) -> None:
        self.ident = ident
        self.done: asyncio.Future[bool] = asyncio.get_running_loop().create_future()

    def datagram_received(self, data: bytes, addr: Any) -> None:
        if is_answer(data, self.ident) and not self.done.done():
            self.done.set_result(True)

    def error_received(self, exc: Exception) -> None:
        if not self.done.done():
            self.done.set_result(False)


async def dns_answers(host: str, port: int = 53) -> bool:
    """One lookup over UDP: does the server at host answer at all?"""
    ident = secrets.randbelow(0x10000)
    loop = asyncio.get_running_loop()
    try:
        transport, lookup = await loop.create_datagram_endpoint(
            lambda: _Lookup(ident), remote_addr=(host, port))
    except OSError:
        return False
    try:
        transport.sendto(query(PROBE_NAME, ident))
        return await asyncio.wait_for(lookup.done, PROBE_TIMEOUT_SECONDS)
    except TimeoutError:
        return False
    finally:
        transport.close()


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


async def _read(s: dict[str, Any], transport: httpx.AsyncBaseTransport | None,
                now: datetime) -> DnsStats:
    auth = basic_auth(s["user"], s["password"])
    async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS, transport=transport) as client:
        stats = await client.get(f"{s['url']}/control/stats", headers=auth)
        stats.raise_for_status()
        status = await client.get(f"{s['url']}/control/status", headers=auth)
        status.raise_for_status()
    return parse(stats.json(), status.json(), now)


async def collect(cfg: dict[str, Any], store: Store,
                  transport: httpx.AsyncBaseTransport | None = None,
                  now: datetime | None = None, probe: Probe | None = None) -> DnsStats:
    """`transport`, `now` and `probe` are for tests."""
    s = settings(cfg)
    now = now or datetime.now(UTC)
    previous = store.get_cache(CACHE_KEY)
    dns_ok = await (probe or dns_answers)(s["dns"]) if s["dns"] else True
    try:
        fresh: DnsStats | None = await _read(s, transport, now)
    except Exception as exc:
        if not _not_answering(exc) or previous is None:
            raise
        log.warning("AdGuard's admin page is not answering: %s", type(exc).__name__)
        fresh = None
    # With the DNS check, DNS decides: an admin page that is down only leaves old counts.
    failing = "dns" if not dns_ok else "admin" if fresh is None and not s["dns"] else None
    base = fresh.model_dump(mode="json") if fresh is not None else previous | {"stale": True}
    if failing is None:
        return DnsStats.model_validate(base | {"failing": None, "failing_since": None,
                                               "answering": True})
    if failing == "dns":
        log.warning("AdGuard does not answer DNS lookups")
    since = datetime.fromisoformat((previous or {}).get("failing_since") or now.isoformat())
    return DnsStats.model_validate(base | {
        "failing": failing, "failing_since": since, "answering": now - since < GRACE,
    })
