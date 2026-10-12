"""The NAS's Tailscale name, IP and HTTPS ports, and its whole tailnet, from tailscaled's LocalAPI.

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

from ..models import Hosts, Tailnet, TailnetDevice, TailscaleHost

log = logging.getLogger(__name__)

# tailscaled refuses LocalAPI requests for any other Host header.
LOCALAPI_BASE = "http://local-tailscaled.sock"
TAILNET_CACHE_KEY = "tailnet"


def parse_status(status: dict[str, Any]) -> TailscaleHost:
    me = status.get("Self") or {}
    dns_name = (me.get("DNSName") or "").rstrip(".")
    if not dns_name:
        raise ValueError("tailscale status has no DNS name for this node")
    ipv4 = next((ip for ip in me.get("TailscaleIPs") or [] if "." in ip), None)
    return TailscaleHost(dns_name=dns_name, ip=ipv4)


def _when(value: str | None) -> datetime | None:
    """tailscaled writes Go's zero time ("0001-01-01T00:00:00Z") for never."""
    if not value or value.startswith("0001-"):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _device(node: dict[str, Any], *, is_self: bool = False) -> TailnetDevice:
    ips = node.get("TailscaleIPs") or []
    online = bool(node.get("Online")) or is_self
    endpoint = node.get("CurAddr") or None
    relay = node.get("Relay") or None
    if is_self or not online:
        connection = None
    elif endpoint:
        connection = "direct"
    elif node.get("Active") and relay:
        connection = "relay"
    else:
        connection = "idle"
    return TailnetDevice(
        name=node.get("HostName") or "",
        dns_name=(node.get("DNSName") or "").rstrip("."),
        os=node.get("OS") or "",
        ipv4=next((ip for ip in ips if "." in ip), None),
        ipv6=next((ip for ip in ips if ":" in ip), None),
        online=online,
        last_seen=None if online else _when(node.get("LastSeen")),
        connection=connection,
        # A direct peer's home relay says nothing about this connection.
        relay=relay if is_self or connection == "relay" else None,
        endpoint=endpoint if connection == "direct" else None,
        exit_node=bool(node.get("ExitNodeOption")),
        rx_bytes=int(node.get("RxBytes") or 0),
        tx_bytes=int(node.get("TxBytes") or 0),
    )


def parse_tailnet(status: dict[str, Any], now: datetime) -> Tailnet:
    me = status.get("Self") or {}
    if not me.get("DNSName"):
        raise ValueError("tailscale status has no DNS name for this node")
    tailnet = status.get("CurrentTailnet") or {}
    suffix = status.get("MagicDNSSuffix") or tailnet.get("MagicDNSSuffix") or ""
    peers = [
        _device(p)
        for p in (status.get("Peer") or {}).values()
        # Mullvad exit nodes carry a Location; with that add-on there are hundreds.
        if p and not p.get("Location")
    ]
    peers.sort(key=lambda d: (not d.online, d.name.lower()))
    return Tailnet(
        as_of=now,
        stale=False,
        name=suffix.split(".")[0],
        self=_device(me, is_self=True),
        peers=peers,
        health=[h for h in status.get("Health") or [] if h],
    )


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


def _client(socket_path: str) -> httpx.AsyncClient:
    if not Path(socket_path).exists():
        raise FileNotFoundError(f"tailscaled socket {socket_path} not present")
    transport = httpx.AsyncHTTPTransport(uds=socket_path)
    return httpx.AsyncClient(transport=transport, base_url=LOCALAPI_BASE)


async def status(socket_path: str) -> TailscaleHost:
    async with _client(socket_path) as client:
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


async def collect_tailnet(cfg: dict[str, Any]) -> Tailnet:
    """Every device on the tailnet. Raises when tailscaled cannot be read, so
    the last good answer stays cached, flagged stale."""
    async with _client(cfg["tailscale"]["socket"]) as client:
        resp = await client.get("/localapi/v0/status", timeout=5)
        resp.raise_for_status()
        return parse_tailnet(resp.json(), datetime.now(UTC))
