"""The hub's MCP server at /mcp (plan.md M33): Claude asks the house over the tailnet.

Read-only tools over the collector's own cache, so a call never waits on a source and
never reaches one. Whatever a tool returns goes into a prompt at Anthropic, so each tool
returns the least that answers: the cached payload trimmed, never more than `/api` serves.

No login, like the rest of the hub (the LAN and Tailscale are the boundary). A browser
has no business here, so any request with an Origin header is refused: that keeps another
website, or a DNS rebinding trick, from asking on the owner's behalf.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from mcp.server.mcpserver import MCPServer
from mcp.server.streamable_http_manager import StreamableHTTPASGIApp
from mcp.server.transport_security import TransportSecuritySettings
from mcp_types import ToolAnnotations
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from .sources import ns
from .store import Store

PATH = "/mcp"

INSTRUCTIONS = (
    "The Home hub of one household: the NAS, its backups and the owner's weekday train. "
    "Every answer is the hub's last good reading; `stale: true` means a source failed and "
    "this is older than usual, `as_of` says from when."
)

READ_ONLY = ToolAnnotations(read_only_hint=True, open_world_hint=False)


def _missing(what: str) -> dict[str, Any]:
    return {"available": False, "reason": f"The hub has no {what} data yet (just started?)."}


def _run(run: dict[str, Any] | None, with_stops: bool) -> dict[str, Any] | None:
    if not run:
        return None
    out = {
        "name": run.get("name"),
        "status": run.get("status"),
        "planned_departure": run.get("planned_departure"),
        "actual_departure": run.get("actual_departure"),
        "delay_minutes": run.get("delay_minutes", 0),
        "track": run.get("actual_track") or run.get("planned_track"),
    }
    if with_stops:
        out["stops"] = [stop.get("name") for stop in run.get("stops") or []]
    return out


def train_summary(payload: dict[str, Any] | None) -> dict[str, Any]:
    """The weekday train as the Home card knows it; the stops by name only."""
    if payload is None:
        return _missing("train")
    return {
        "as_of": payload.get("as_of"),
        "stale": payload.get("stale", False),
        "date": payload.get("date"),
        "route": payload.get("route"),
        "departure": payload.get("departure"),
        "mode": payload.get("mode"),
        "watching": payload.get("watching"),
        "departed": payload.get("departed"),
        "train": _run(payload.get("train"), with_stops=True),
        "next_direct": _run(payload.get("next_direct"), with_stops=False),
    }


def backups_summary(payload: dict[str, Any] | None) -> dict[str, Any]:
    """Per volume the last run and last success, the storage box's room and the next run."""
    if payload is None:
        return _missing("backup")
    volumes = []
    for summary in payload.get("volumes") or []:
        run = summary.get("last_run") or {}
        mine = next((v for v in run.get("volumes") or [] if v.get("name") == summary.get("name")),
                    {})
        volumes.append({
            "name": summary.get("name"),
            "last_run_finished": run.get("finished"),
            "last_run_ok": mine.get("ok"),
            "last_run_errors": mine.get("errors"),
            "last_error": mine.get("last_error"),
            "last_success": summary.get("last_success"),
        })
    box = payload.get("storage_box")
    return {
        "as_of": payload.get("as_of"),
        "stale": payload.get("stale", False),
        "next_due": payload.get("next_due"),
        "volumes": volumes,
        "storage_box": box and {
            "used_pct": box.get("used_pct"),
            "free_bytes": box.get("free"),
            "months_until_full": box.get("projection_months"),
        },
    }


def nas_summary(payload: dict[str, Any] | None) -> dict[str, Any]:
    """The NAS's health now: load, temperatures, storage, disks, containers; no history."""
    if payload is None:
        return _missing("NAS")
    out = dict(payload)
    network = out.get("network")
    if isinstance(network, dict):
        out["network"] = {k: v for k, v in network.items() if k != "history"}
    return out


def build(store: Callable[[], Store]) -> MCPServer:
    """The server; `store` is asked on each call, so tests and the app can swap it."""
    server = MCPServer("home-hub", instructions=INSTRUCTIONS)

    @server.tool(annotations=READ_ONLY)
    def train() -> dict[str, Any]:
        """The owner's weekday morning train: on weekday mornings until it leaves, the evening
        before for tomorrow's. Status, delay, track, cancellation with the next direct train."""
        return train_summary(store().get_cache(ns.CACHE_KEY))

    @server.tool(annotations=READ_ONLY)
    def backups() -> dict[str, Any]:
        """The nightly backup to the Hetzner storage box: per volume the last run and last
        success, the box's free room and when it fills up, and the next run."""
        return backups_summary(store().get_cache("backups"))

    @server.tool(annotations=READ_ONLY)
    def nas() -> dict[str, Any]:
        """The NAS right now: CPU, memory, temperatures, storage, disks with SMART state,
        running containers, network speed and the last backup's state."""
        return nas_summary(store().get_cache("nas"))

    return server


class _RefuseBrowsers:
    """403 for any request carrying an Origin header (see the module docstring)."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http" and any(k == b"origin" for k, _ in scope["headers"]):
            response = JSONResponse({"detail": "Not for browsers."}, status_code=403)
            await response(scope, receive, send)
            return
        await self.app(scope, receive, send)


def http_endpoint(server: MCPServer) -> ASGIApp:
    """The ASGI endpoint to route at PATH.

    Stateless and plain JSON (no event stream): every tool answers at once from the
    cache, and Caddy passes it on like any API call. The SDK's own Host check is off:
    the hub answers on several names (LAN, Tailscale), and the Origin check covers it.
    It answers only while `server.session_manager.run()` runs (the app's lifespan).
    """
    # Builds the server's session manager; the SDK's own Starlette app is not used.
    server.streamable_http_app(
        streamable_http_path=PATH,
        stateless_http=True,
        json_response=True,
        transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False),
    )
    return _RefuseBrowsers(StreamableHTTPASGIApp(server.session_manager))
