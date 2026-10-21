"""Download widgets: SABnzbd and Transmission.

Checked against each project's source (2026-09):
- SABnzbd: /api?mode=queue. The key is only accepted as the `apikey` query
  parameter, so it is in the URL: never log URLs (see main.py).
- Transmission: /transmission/rpc behind the X-Transmission-Session-Id
  handshake (a 409 hands out the id). 4.1 speaks JSON-RPC 2.0 with snake_case
  names; the old protocol is deprecated but still what 4.0 speaks, so it is
  the fallback. It only answers a request addressed to an IP address or a name
  in its rpc-host-whitelist (against DNS rebinding); host.docker.internal is
  neither (421 Misdirected Request), so it is called by address.
"""

from __future__ import annotations

import asyncio
import ipaddress
import socket
from typing import Any

import httpx

from ...models import Stat
from .http import expect, get

KIBI = 1024
MEBI = 1024 * 1024
SESSION_HEADER = "X-Transmission-Session-Id"


async def sabnzbd(client: httpx.AsyncClient, base_url: str, key: str) -> list[Stat]:
    body = expect(
        await get(client, f"{base_url}/api", {}, mode="queue", output="json", apikey=key), dict
    )
    queue = expect(body.get("queue"), dict)
    return [
        Stat(label="Queued", value=int(queue["noofslots"])),
        Stat(label="Down", value=float(queue["kbpersec"]) * KIBI, unit="bytes_per_second"),
        Stat(label="Left", value=float(queue["mbleft"]) * MEBI, unit="bytes"),
    ]


async def _lookup(host: str, port: int | None) -> str:
    """The host's IPv4 address; OSError when it has none."""
    infos = await asyncio.get_running_loop().getaddrinfo(
        host, port, family=socket.AF_INET, type=socket.SOCK_STREAM)
    return infos[0][4][0]


async def _by_address(base_url: str) -> str:
    """`base_url` with its host name replaced by the address, for Transmission's
    host check; unchanged for an address, localhost, or a name that does not resolve."""
    url = httpx.URL(base_url)
    try:
        ipaddress.ip_address(url.host)
        return base_url
    except ValueError:
        pass
    if url.host == "localhost":
        return base_url
    try:
        return str(url.copy_with(host=await _lookup(url.host, url.port))).rstrip("/")
    except OSError:
        return base_url


async def _rpc(client: httpx.AsyncClient, url: str, payload: dict[str, Any]) -> dict[str, Any]:
    """POST with the session-id handshake: the first 409 carries the id to retry with."""
    resp = await client.post(url, json=payload)
    if resp.status_code == 409 and SESSION_HEADER in resp.headers:
        headers = {SESSION_HEADER: resp.headers[SESSION_HEADER]}
        resp = await client.post(url, json=payload, headers=headers)
    resp.raise_for_status()
    return expect(resp.json(), dict)


async def transmission(client: httpx.AsyncClient, base_url: str, key: str) -> list[Stat]:
    url = f"{await _by_address(base_url)}/transmission/rpc"
    reply = await _rpc(client, url, {"jsonrpc": "2.0", "method": "session_stats", "id": 1})
    stats = reply.get("result")
    if isinstance(stats, dict):
        active, down, up = "active_torrent_count", "download_speed", "upload_speed"
    else:
        # Before 4.1: no JSON-RPC, camelCase fields under "arguments".
        reply = await _rpc(client, url, {"method": "session-stats"})
        stats = expect(reply.get("arguments"), dict)
        active, down, up = "activeTorrentCount", "downloadSpeed", "uploadSpeed"
    return [
        Stat(label="Active", value=stats[active]),
        Stat(label="Down", value=stats[down], unit="bytes_per_second"),
        Stat(label="Up", value=stats[up], unit="bytes_per_second"),
    ]
