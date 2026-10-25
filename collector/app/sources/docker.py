"""Container state over the Docker socket, read-only.

One `GET /containers/json?all=1` gives every container with its state and, for
those with a healthcheck, the health in the human `Status` string. Used by the
NAS container counts and by the service status dots.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

from ..models import ContainerList, ContainerState

log = logging.getLogger(__name__)

# "Up 3 hours (healthy)", "Up 5 seconds (health: starting)", "Up 2 days (unhealthy)"
_HEALTH = re.compile(r"\((healthy|unhealthy|health: starting)\)")


def parse(raw: list[dict[str, Any]]) -> list[ContainerState]:
    containers: list[ContainerState] = []
    for entry in raw:
        names = entry.get("Names") or []
        if not names:
            continue
        match = _HEALTH.search(entry.get("Status") or "")
        health = match.group(1).replace("health: ", "") if match else None
        labels = entry.get("Labels") or {}
        containers.append(
            ContainerState(
                name=names[0].lstrip("/"),
                state=entry.get("State") or "unknown",
                health=health,
                id=entry.get("Id") or "",
                image=entry.get("Image") or "",
                image_id=entry.get("ImageID") or "",
                project=labels.get("com.docker.compose.project"),
                status=entry.get("Status") or "",
                version=labels.get("org.opencontainers.image.version"),
                source=labels.get("org.opencontainers.image.source"),
            )
        )
    containers.sort(key=lambda c: c.name)
    return containers


async def list_containers(
    socket_path: str, transport: httpx.AsyncBaseTransport | None = None
) -> list[ContainerState] | None:
    """Every container, running or not; None when the socket is unavailable
    (off-NAS development, or the mount is missing). `transport` is for tests."""
    if transport is None and not Path(socket_path).exists():
        log.info("docker socket %s not present", socket_path)
        return None
    try:
        transport = transport or httpx.AsyncHTTPTransport(uds=socket_path)
        async with httpx.AsyncClient(transport=transport, base_url="http://docker") as client:
            resp = await client.get("/containers/json", params={"all": "1"}, timeout=5)
            resp.raise_for_status()
            return parse(resp.json())
    except Exception as exc:
        log.warning("docker socket read failed: %s: %s", type(exc).__name__, exc)
        return None


async def collect(cfg: dict[str, Any]) -> ContainerList:
    containers = await list_containers(cfg["nas"]["docker_socket"])
    if containers is None:
        # Raise so the scheduler keeps the last list and flags it stale.
        raise RuntimeError("docker socket unavailable")
    return ContainerList(as_of=datetime.now(UTC), stale=False, containers=containers)


async def die_counts(
    socket_path: str, since: datetime, until: datetime,
    transport: httpx.AsyncBaseTransport | None = None,
) -> dict[str, int] | None:
    """How often each container stopped ("die" events) between since and until;
    None when the socket is unavailable. With `until` set, Docker returns the
    events and closes the response instead of streaming."""
    if transport is None and not Path(socket_path).exists():
        return None
    params = {
        "since": str(int(since.timestamp())),
        "until": str(int(until.timestamp())),
        "filters": json.dumps({"type": ["container"], "event": ["die"]}),
    }
    try:
        transport = transport or httpx.AsyncHTTPTransport(uds=socket_path)
        async with httpx.AsyncClient(transport=transport, base_url="http://docker") as client:
            resp = await client.get("/events", params=params, timeout=10)
            resp.raise_for_status()
    except Exception as exc:
        log.warning("docker events read failed: %s", type(exc).__name__)
        return None
    counts: dict[str, int] = {}
    for line in resp.text.splitlines():
        try:
            event = json.loads(line)
        except ValueError:
            continue
        name = ((event.get("Actor") or {}).get("Attributes") or {}).get("name")
        if name:
            counts[name] = counts.get(name, 0) + 1
    return counts
