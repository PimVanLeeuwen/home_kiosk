"""The MCP developer tools (plan.md M34): for Claude Code sessions that work on the hub, the
panels and nas-docker. Read-only, like the house tools, and on the same servers.

Decided 2026-11-12: container logs of any container, redacted as the alert explainer does;
raw source payloads with their values except for the personal sources, which show their
shape only; the panels' state instead of a screenshot (that needs USB); no compose drift
(it would need every stack's .env inside the hub).
"""

from __future__ import annotations

import re
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
from apscheduler.schedulers.base import BaseScheduler
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp_types import ToolAnnotations

from . import desk, desk_boards, logbuffer, scheduler
from .explainer import demux, redact
from .store import Store

READ_ONLY = ToolAnnotations(read_only_hint=True, open_world_hint=False)

# Sources whose values are the household's own: names, events, money, who watched what.
# `source_sample` shows only their shape; so does any key not named in VALUES.
VALUES = {
    "air", "apple", "backups", "containers", "dns", "docker", "dumps", "forecast",
    "github-mirror", "headlines", "hosts", "indices", "laundry", "lights", "media", "nas",
    "news", "news_full", "outside_services", "pipelines", "radar", "repos", "sites", "train",
    "ups", "weather", "widgets",
}
LIST_ITEMS = 3  # a sample keeps this many items of every list
TEXT_CHARS = 300
CONTAINER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")
MAX_LOG_LINES = 200
LOG_CHARS = 20000
REVISION = "org.opencontainers.image.revision"
HUB_IMAGES = ("pimvanleeuwen/home-kiosk-collector", "pimvanleeuwen/home-kiosk-dashboard")


def shape(value: Any) -> Any:
    """Field names and types, no values; a list as its first item's shape and its length."""
    if isinstance(value, dict):
        return {k: shape(v) for k, v in value.items()}
    if isinstance(value, list):
        return {"list_of": shape(value[0]) if value else None, "length": len(value)}
    return type(value).__name__


def sample(value: Any) -> Any:
    """The values, with every list cut to its first items and long text cut short."""
    if isinstance(value, dict):
        return {k: sample(v) for k, v in value.items()}
    if isinstance(value, list):
        kept = [sample(v) for v in value[:LIST_ITEMS]]
        return kept + ([f"... {len(value) - LIST_ITEMS} more"] if len(value) > LIST_ITEMS else [])
    if isinstance(value, str) and len(value) > TEXT_CHARS:
        return value[:TEXT_CHARS] + "..."
    return value


def cache_keys(store: Store) -> list[dict[str, Any]]:
    with store.connect() as conn:
        rows = conn.execute("SELECT key, fetched_at, length(payload_json) AS size FROM cache "
                            "ORDER BY key").fetchall()
    return [{"key": r["key"], "fetched_at": r["fetched_at"], "bytes": r["size"],
             "values": r["key"] in VALUES} for r in rows]


def _when(value: datetime | None) -> str | None:
    return value.isoformat(timespec="seconds") if value else None


def jobs(sched: BaseScheduler | None) -> list[dict[str, Any]]:
    """Every scheduled job: when it runs next, when it last ran and how its refresh went."""
    if sched is None:
        return []
    out = []
    for job in sched.get_jobs():
        key = job.args[1] if job.func is scheduler._run and len(job.args) > 1 else None
        ran = scheduler.RUNS.get(job.id) or {}
        refresh = scheduler.REFRESHES.get(key) if key else None
        out.append({
            "id": job.id,
            "trigger": str(job.trigger),
            "next_run": _when(getattr(job, "next_run_time", None)),  # unset until started
            "last_run": _when(ran.get("at")),
            "missed": ran.get("missed", False),
            "error": (refresh or {}).get("error") or ran.get("error"),
            "ok": refresh["ok"] if refresh else (not ran.get("error") if ran else None),
            "cache_key": key,
        })
    return out


def _docker(socket: str, transport: httpx.AsyncBaseTransport | None) -> httpx.AsyncClient:
    if transport is None and not Path(socket).exists():
        raise ToolError("The Docker socket is not there (not on the NAS?).")
    return httpx.AsyncClient(transport=transport or httpx.AsyncHTTPTransport(uds=socket),
                             base_url="http://docker", timeout=10)


async def container_logs(socket: str, name: str, lines: int,
                         transport: httpx.AsyncBaseTransport | None = None) -> dict[str, Any]:
    if not CONTAINER.match(name):
        raise ToolError("A container is named by its name, like home-kiosk-collector.")
    lines = min(max(lines, 1), MAX_LOG_LINES)
    async with _docker(socket, transport) as client:
        resp = await client.get(f"/containers/{name}/logs", params={
            "stdout": "1", "stderr": "1", "tail": str(lines), "timestamps": "1"})
    if resp.status_code == 404:
        raise ToolError(f"No container called {name!r}; see the docker tool for the names.")
    if resp.status_code >= 400:
        raise ToolError(f"Docker answered {resp.status_code}.")
    text = redact(demux(resp.content))[-LOG_CHARS:]
    return {"container": name, "lines": lines, "log": text}


async def deployed(socket: str, pipelines: dict[str, Any] | None,
                   transport: httpx.AsyncBaseTransport | None = None) -> dict[str, Any]:
    """The hub's two containers: the commit their images were built from (the revision label
    CI puts on them), and home_kiosk's latest CI run on main as the hub last saw it."""
    async with _docker(socket, transport) as client:
        resp = await client.get("/containers/json", params={"all": "1"})
    resp.raise_for_status()
    running = []
    for c in resp.json():
        image = c.get("Image") or ""
        if image.split(":")[0] in HUB_IMAGES:
            running.append({"name": (c.get("Names") or ["?"])[0].lstrip("/"), "image": image,
                            "image_id": (c.get("ImageID") or "")[7:19], "state": c.get("State"),
                            "status": c.get("Status"),
                            "revision": (c.get("Labels") or {}).get(REVISION)})
    repo = next((r for r in (pipelines or {}).get("repos") or []
                 if r.get("name") == "home_kiosk"), None)
    run = (repo or {}).get("run")
    return {
        "containers": running,
        "latest_ci_run": run and {k: run.get(k) for k in
                                  ("sha", "commit", "state", "started_at", "ended_at", "failed")},
        "note": None if any(c["revision"] for c in running) else
        "No revision label yet: images built before CI added it (plan.md M34).",
    }


def panels(cfg: dict[str, Any], store: Store) -> list[dict[str, Any]]:
    """Every desk board the hub knows, and what it would send each one now: the screens by
    kind (no content) and the answer's size before it is fitted to the board."""
    out = []
    for board in desk_boards.boards(store):
        item = board.model_dump(mode="json")
        if board.panel:
            answer = desk.answer(cfg, store, board.panel, board=board.mac)
            item["screens"] = [{"kind": s.get("kind"), "present": s.get("present", True)}
                               for s in answer.get("screens") or []]
            item["rotates"] = answer.get("rotate")
            # Before fitting: each board says how much it can read with every request
            # (`room`), which the hub does not keep; desk.fit leaves screens out past it.
            item["answer_bytes"] = desk.size(answer)
        out.append(item)
    return out


def register(server: MCPServer, store: Callable[[], Store],
             config: Callable[[], dict[str, Any]],
             sched: Callable[[], BaseScheduler | None]) -> None:
    tool = server.tool(annotations=READ_ONLY)

    def socket() -> str:
        return ((config().get("nas") or {}).get("docker_socket")) or "/var/run/docker.sock"

    @tool
    def source_sample(key: str | None = None) -> dict[str, Any]:
        """A source's payload as the hub cached it, for building on its real shape. Without
        `key`: every cache key with its age and size. Personal sources (calendar, birthdays,
        portfolio, photos, who watched what, ...) show field names and types only; the rest
        their values, every list cut to its first 3 items."""
        s = store()
        if not key:
            return {"keys": cache_keys(s)}
        payload = s.get_cache(key)
        if payload is None:
            raise ToolError(f"Nothing cached under {key!r}; call without a key for the list.")
        if key in VALUES:
            return {"key": key, "values": True, "payload": sample(payload)}
        return {"key": key, "values": False, "shape": shape(payload)}

    @tool
    def job_status() -> dict[str, Any]:
        """The collector's scheduled jobs: trigger, next run, last run, and whether the last
        refresh worked (with the error's class when not). Since the collector last started."""
        return {"now": datetime.now(UTC).isoformat(timespec="seconds"),
                "jobs": jobs(sched())}

    @tool
    def hub_logs(minutes: int = 60, level: str = "INFO", limit: int = 100) -> dict[str, Any]:
        """The collector's own log from the last `minutes` (oldest first, at most `limit`,
        up to 500), from `level` up (INFO, WARNING, ERROR), redacted. Kept in memory since
        the collector last started."""
        return {"records": logbuffer.recent(minutes, level, limit)}

    @server.tool(name="container_logs", annotations=READ_ONLY)
    async def container_logs_tool(name: str, lines: int = 100) -> dict[str, Any]:
        """The last `lines` (up to 200) of any container's log on the NAS, with timestamps,
        redacted (emails, IP addresses, tokens and secrets removed)."""
        return await container_logs(socket(), name, lines)

    @tool
    async def deployed_version() -> dict[str, Any]:
        """Which commit the hub's containers on the NAS run (their images' revision), and
        home_kiosk's latest CI run on main: "is my change live yet?"."""
        try:
            return await deployed(socket(), store().get_cache("pipelines"))
        except ToolError:
            raise
        except Exception as exc:
            raise ToolError(f"Docker could not be read ({type(exc).__name__}).") from None

    @tool
    def panel_state() -> dict[str, Any]:
        """The desk panels: each board's panel, when it last asked, its firmware, whether it
        is upside down, and the screens the hub would send it now (kinds only) with the
        answer's size before it is fitted to what the board can read (it says so itself
        with each request; current firmware reads 32 kB)."""
        return {"boards": panels(config(), store())}
