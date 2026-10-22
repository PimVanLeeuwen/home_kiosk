"""The House panel's Tailnet screen (plan.md Open items, designed 2026-10-12): the NAS
in the middle and every device around it, a line per device by how it connects
(direct, through a relay, idle, offline), the exit node marked; below, the NAS and
each online device with its Tailscale address. The warning state is tailscaled's
own health warnings. Ready to draw, from `/api/tailnet` (sources/tailscale.py),
placed as the hub's Tailscale page places them (web/src/lib/tailnet.ts).
"""

from __future__ import annotations

import math
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from .panel_text import latin1
from .sources import tailscale
from .store import Store

MAX_NODES = 8  # round the NAS on the map
MAX_ROWS = 4   # online devices in the list under the NAS
# Short names on the tiles, by kind of device (as the page's icons choose them).
LABELS = {"tablet": "iPd", "laptop": "Mac", "phone": "iP", "android": "And", "tv": "TV",
          "desktop": "PC", "server": "Lx"}


def _label(device: dict[str, Any]) -> str:
    if any(w in device["name"].lower() for w in ("ipad", "tablet")):
        return LABELS["tablet"]
    return LABELS.get({"macOS": "laptop", "iOS": "phone", "android": "android", "tvOS": "tv",
                       "windows": "desktop"}.get(device.get("os") or "", "server"), "Lx")


def _kind(device: dict[str, Any]) -> str:
    if not device.get("online"):
        return "offline"
    return device.get("connection") or "idle"


def _via(device: dict[str, Any]) -> str:
    """"direct", "relay ams", "idle", for the list."""
    kind = _kind(device)
    if kind == "relay" and device.get("relay"):
        return f"relay {device['relay']}"
    return kind


def _seen(last: str | None, now: datetime) -> str:
    """"12 min ago", "5 h ago", "2 days ago"; "" without a time."""
    if not last:
        return ""
    minutes = max(0, int((now - datetime.fromisoformat(last)).total_seconds() // 60))
    if minutes < 60:
        return f"{minutes} min ago"
    if minutes < 48 * 60:
        return f"{minutes // 60} h ago"
    return f"{minutes // (24 * 60)} days ago"


def positions(count: int) -> list[tuple[int, int]]:
    """Where each device sits, in percent of the map: evenly round an ellipse around
    the NAS, starting top left, so four devices take the corners."""
    spots = []
    for i in range(count):
        angle = math.radians(-90 - 180 / count + 360 / count * i)
        spots.append((round(50 + 40 * math.cos(angle)), round(48 + 39 * math.sin(angle))))
    return spots


def tailnet_screen(store: Store, zone: ZoneInfo, now: datetime) -> dict[str, Any]:
    data = store.get_cache(tailscale.TAILNET_CACHE_KEY)
    if not data or not data.get("self"):
        return {"kind": "tailnet", "stale": False, "present": False}
    peers = (data.get("peers") or [])[:MAX_NODES]  # online first already
    health = [latin1(h) for h in data.get("health") or []]
    online = [p for p in peers if p.get("online")]
    nodes = [{
        "label": _label(p), "name": latin1(p["name"]), "kind": _kind(p),
        "exit": bool(p.get("exit_node")),
        "seen": "" if p.get("online") else _seen(p.get("last_seen"), now),
        "x": x, "y": y,
    } for p, (x, y) in zip(peers, positions(len(peers)), strict=True)]
    me = data["self"]
    return {
        "kind": "tailnet",
        "stale": bool(data.get("stale")),
        "present": True,
        "title": f"TAILNET · {latin1(data.get('name') or '').upper()}".rstrip(" ·"),
        "status": (f"{len(health)} HEALTH ISSUE{'S' if len(health) != 1 else ''}" if health
                   else f"{len(online) + 1} OF {len(peers) + 1} ONLINE"),
        "warn": bool(health),
        "nodes": nodes,
        "rows": [{"name": latin1(me["name"]), "ip": me.get("ipv4") or "",
                  "via": health[0] if health else "this NAS", "kind": "self"}]
        + [{"name": latin1(p["name"]), "ip": p.get("ipv4") or "", "via": _via(p), "kind": _kind(p)}
           for p in online[:MAX_ROWS]],
    }
