"""The NAS's own Tailscale name, IP and HTTPS ports, from tailscaled's LocalAPI.

The tailscale container shares its control socket through a bind mount (see
the compose file). Only reads: `GET /localapi/v0/status` and
`GET /localapi/v0/serve-config`.
"""

from __future__ import annotations

import logging
import re
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


_LOCAL_TARGET = re.compile(r"^(?:https?|https\+insecure)://(?:127\.0\.0\.1|localhost):(\d+)/?$")


def parse_serve_config(config: dict[str, Any]) -> dict[str, int]:
    """Map each proxied local port to the HTTPS port it is served on.

    Reads the `Web` section of ipn.ServeConfig, keyed "<host>:<port>" with a
    "/" handler proxying to http://127.0.0.1:<local port>. Other handlers
    (paths, files, text) are not service links and are skipped.
    """
    served: dict[str, int] = {}
    for host_port, web in (config.get("Web") or {}).items():
        _, _, port = host_port.rpartition(":")
        root = ((web or {}).get("Handlers") or {}).get("/") or {}
        match = _LOCAL_TARGET.match(root.get("Proxy") or "")
        if port.isdigit() and match:
            served[match.group(1)] = int(port)
    return served


async def status(socket_path: str) -> TailscaleHost:
    if not Path(socket_path).exists():
        raise FileNotFoundError(f"tailscaled socket {socket_path} not present")
    transport = httpx.AsyncHTTPTransport(uds=socket_path)
    async with httpx.AsyncClient(transport=transport, base_url=LOCALAPI_BASE) as client:
        resp = await client.get("/localapi/v0/status", timeout=5)
        resp.raise_for_status()
        host = parse_status(resp.json())
        try:
            serve = await client.get("/localapi/v0/serve-config", timeout=5)
            serve.raise_for_status()
            host.https_ports = parse_serve_config(serve.json() or {})
        except Exception as exc:
            # Links then fall back to plain HTTP; the name and IP still count.
            log.warning("tailscale serve config unreadable: %s", type(exc).__name__)
        return host


async def collect(cfg: dict[str, Any]) -> Hosts:
    """Raises when tailscaled cannot be read, so the last good hosts stay
    cached (flagged stale) rather than losing the tailnet name."""
    return Hosts(
        as_of=datetime.now(UTC),
        stale=False,
        lan=cfg["hosts"]["lan"],
        tailscale=await status(cfg["tailscale"]["socket"]),
    )
