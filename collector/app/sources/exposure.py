"""Exposure audit: what of the house can be reached from the internet.

A few services (CouchDB, Jellyfin, Uptime Kuma) are public through a Cloudflare
tunnel, which connects outward from the NAS, so the router needs no open port and
nothing else may answer. Every 6 hours the collector asks Cloudflare, with a read-only API token
(Zone DNS Read, Account Cloudflare Tunnel Read), for the zone's DNS records and
every tunnel's public hostnames, and requests each of those hostnames over
HTTPS. The requests go out through Cloudflare, so they see what an outsider
sees. A hostname that leads to the house and is not on the allowlist is an
error alert: a tunnel route, a CNAME to a tunnel, or an A/AAAA record on the
home IP (learned from Cloudflare's own cdn-cgi/trace).

Open ports on the home IP itself can only be seen from outside the house; a
nightly GitHub Action scans for those (M14 step 2).
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from typing import Any, Literal

import httpx

from ..models import Exposure, PublicHost
from ..store import Store

log = logging.getLogger(__name__)

CACHE_KEY = "exposure"
API = "https://api.cloudflare.com/client/v4"
TRACE = "https://www.cloudflare.com/cdn-cgi/trace"
TIMEOUT_SECONDS = 15
MAX_PAGES = 10


Source = Literal["tunnel", "dns"]
Found = tuple[str, Source, str]  # hostname, how it leads to the house, target


class AuditError(Exception):
    """A failure with a message fit for the page, never the token."""


def settings(cfg: dict[str, Any]) -> dict[str, Any]:
    ex = cfg.get("exposure") or {}
    return {
        "token": (ex.get("cloudflare_token") or "").strip(),
        "zone": ex.get("zone", ""),
        "allowed": {h.strip().lower() for h in ex.get("allowed", []) if h and h.strip()},
        "enabled": bool(ex.get("zone")),
    }


async def _get(client: httpx.AsyncClient, path: str, **params: Any) -> Any:
    resp = await client.get(f"{API}{path}", params=params)
    if resp.status_code in (401, 403):
        raise AuditError(f"Cloudflare refused the token ({resp.status_code}); "
                         "it needs Zone DNS Read and Account Cloudflare Tunnel Read")
    resp.raise_for_status()
    body = resp.json()
    if not body.get("success", False):
        raise AuditError("Cloudflare answered with an error")
    return body


async def _pages(client: httpx.AsyncClient, path: str, **params: Any) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for page in range(1, MAX_PAGES + 1):
        body = await _get(client, path, page=page, per_page=100, **params)
        items += body.get("result") or []
        info = body.get("result_info") or {}
        if page >= (info.get("total_pages") or 1):
            break
    return items


async def home_ip(client: httpx.AsyncClient) -> str | None:
    """The house's public IP, as Cloudflare sees it."""
    try:
        resp = await client.get(TRACE)
        resp.raise_for_status()
    except httpx.HTTPError:
        return None
    for line in resp.text.splitlines():
        if line.startswith("ip="):
            return line[3:].strip()
    return None


async def public_hosts(client: httpx.AsyncClient, zone: str, ip: str | None) -> list[Found]:
    """(hostname, source, target) for every name that leads to the house."""
    zones = (await _get(client, "/zones", name=zone)).get("result") or []
    if not zones:
        raise AuditError(f"The token cannot see the zone {zone}")
    zone_id, account_id = zones[0]["id"], zones[0]["account"]["id"]

    found: dict[str, Found] = {}
    for tunnel in await _pages(client, f"/accounts/{account_id}/cfd_tunnel", is_deleted="false"):
        path = f"/accounts/{account_id}/cfd_tunnel/{tunnel['id']}/configurations"
        config = ((await _get(client, path)).get("result") or {}).get("config") or {}
        for rule in config.get("ingress") or []:
            if rule.get("hostname"):
                name = rule["hostname"].lower()
                found[name] = (name, "tunnel", str(rule.get("service", "")))
    for record in await _pages(client, f"/zones/{zone_id}/dns_records"):
        name, kind, content = record["name"].lower(), record["type"], str(record.get("content", ""))
        to_tunnel = kind == "CNAME" and content.endswith(".cfargotunnel.com")
        to_house = kind in ("A", "AAAA") and ip is not None and content == ip
        if (to_tunnel or to_house) and name not in found:
            found[name] = (name, "dns", f"{kind} {content}")
    return sorted(found.values())


async def probe(client: httpx.AsyncClient, hostname: str) -> tuple[int | None, str | None]:
    """The HTTPS answer for a hostname, without following redirects."""
    try:
        resp = await client.get(f"https://{hostname}/", follow_redirects=False)
        return resp.status_code, None
    except httpx.TimeoutException:
        return None, "timed out"
    except httpx.HTTPError:
        return None, "no answer"


async def collect(cfg: dict[str, Any], store: Store,
                  transport: httpx.AsyncBaseTransport | None = None) -> Exposure:
    """`transport` is for tests (httpx.MockTransport)."""
    ex = settings(cfg)
    previous = store.get_cache(CACHE_KEY) or {}
    now = datetime.now(UTC)
    try:
        if not ex["token"]:
            raise AuditError("No Cloudflare API token set (CLOUDFLARE_API_TOKEN)")
        async with httpx.AsyncClient(
            timeout=TIMEOUT_SECONDS, transport=transport,
            headers={"Authorization": f"Bearer {ex['token']}"},
        ) as api, httpx.AsyncClient(timeout=TIMEOUT_SECONDS, transport=transport) as web:
            ip = await home_ip(web)
            names = await public_hosts(api, ex["zone"], ip)
            answers = await asyncio.gather(*(probe(web, name) for name, _, _ in names))
    except (AuditError, httpx.HTTPError) as exc:
        reason = str(exc) if isinstance(exc, AuditError) else "Cloudflare not reachable"
        log.warning("exposure audit failed: %s", type(exc).__name__)
        return Exposure(as_of=now, zone=ex["zone"], home_ip=previous.get("home_ip"),
                        hosts=[PublicHost.model_validate(h) for h in previous.get("hosts", [])],
                        error=reason)
    hosts = [
        PublicHost(hostname=name, source=source, target=target,
                   allowed=name in ex["allowed"], status=status, error=error)
        for (name, source, target), (status, error) in zip(names, answers, strict=True)
    ]
    return Exposure(as_of=now, zone=ex["zone"], home_ip=ip, hosts=hosts)
