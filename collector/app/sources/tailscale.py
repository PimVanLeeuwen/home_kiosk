"""The NAS's own Tailscale name and IP, from tailscaled's LocalAPI.

The tailscale container shares its control socket through a bind mount (see
the compose file). Only `GET /localapi/v0/status` is used: a read.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

from ..models import Hosts, TailscaleHost

log = logging.getLogger(__name__)

# tailscaled refuses LocalAPI requests for any other Host header.
LOCALAPI_BASE = "http://local-tailscaled.sock"


def parse_status(status: dict[str, Any]) -> TailscaleHost:
    me = status.get("Self") or {}
    dns_name = (me.get("DNSName") or "").rstrip(".")
    if not dns_name:
        raise ValueError("tailscale status has no DNS name for this node")
    ipv4 = next((ip for ip in me.get("TailscaleIPs") or [] if "." in ip), None)
    return TailscaleHost(dns_name=dns_name, ip=ipv4)


async def status(socket_path: str) -> TailscaleHost:
    if not Path(socket_path).exists():
        raise FileNotFoundError(f"tailscaled socket {socket_path} not present")
    transport = httpx.AsyncHTTPTransport(uds=socket_path)
    async with httpx.AsyncClient(transport=transport, base_url=LOCALAPI_BASE) as client:
        resp = await client.get("/localapi/v0/status", timeout=5)
        resp.raise_for_status()
        return parse_status(resp.json())


async def collect(cfg: dict[str, Any]) -> Hosts:
    """Raises when tailscaled cannot be read, so the last good hosts stay
    cached (flagged stale) rather than losing the tailnet name."""
    return Hosts(
        as_of=datetime.now(UTC),
        stale=False,
        lan=cfg["hosts"]["lan"],
        tailscale=await status(cfg["tailscale"]["socket"]),
    )
