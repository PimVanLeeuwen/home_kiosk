"""Per-container load for the Docker page, and a log of image updates.

Every minute: one one-shot `GET /containers/{id}/stats` per running container
(read-only; one-shot skips Docker's own two-sample wait). CPU and network are
rates, so each reading is compared with the previous one, kept in the cache
table like the NAS counters. Readings go to `container_sample` (24h).

Updates are noticed rather than reported: when a container's image ID differs
from last time, it was recreated from a new image, whether by Watchtower or by
hand in Dockge.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from typing import Any

import httpx

from ..models import ContainerLoad, ContainerPoint, ContainerState, DockerOverview
from ..store import Store
from . import docker

log = logging.getLogger(__name__)

COUNTERS_KEY = "container_counters"
IMAGES_KEY = "container_images"
CONCURRENCY = 8


def parse_stats(raw: dict[str, Any]) -> dict[str, Any]:
    """The raw counters this module uses from a stats reading."""
    cpu = raw.get("cpu_stats") or {}
    memory = raw.get("memory_stats") or {}
    mem_detail = memory.get("stats") or {}
    usage = memory.get("usage")
    # Page cache is reclaimable, so `docker stats` leaves it out: inactive_file
    # on cgroup v2, total_inactive_file or cache on v1.
    cache = (
        mem_detail.get("inactive_file")
        or mem_detail.get("total_inactive_file")
        or mem_detail.get("cache")
        or 0
    )
    networks = (raw.get("networks") or {}).values()
    return {
        "cpu_total": (cpu.get("cpu_usage") or {}).get("total_usage"),
        "system_total": cpu.get("system_cpu_usage"),
        "mem_bytes": max(0, usage - cache) if usage is not None else None,
        "mem_limit": memory.get("limit"),
        # Host-network containers have no networks of their own.
        "rx": sum(n.get("rx_bytes", 0) for n in networks) if networks else None,
        "tx": sum(n.get("tx_bytes", 0) for n in networks) if networks else None,
    }


def rates(
    now: dict[str, Any], before: dict[str, Any] | None, elapsed: float
) -> tuple[float | None, float | None, float | None]:
    """CPU share of the whole machine (%) and network bytes per second since `before`."""
    if not before or elapsed <= 0:
        return None, None, None
    cpu = None
    if None not in (now["cpu_total"], now["system_total"], before.get("cpu_total"),
                    before.get("system_total")):
        system_delta = now["system_total"] - before["system_total"]
        cpu_delta = now["cpu_total"] - before["cpu_total"]
        # A restart resets the container's counter: no rate this round.
        if system_delta > 0 and cpu_delta >= 0:
            cpu = round(cpu_delta / system_delta * 100, 2)

    def rate(key: str) -> float | None:
        if now[key] is None or before.get(key) is None or now[key] < before[key]:
            return None
        return round((now[key] - before[key]) / elapsed, 1)

    return cpu, rate("rx"), rate("tx")


async def _stats(client: httpx.AsyncClient, container_id: str) -> dict[str, Any] | None:
    try:
        resp = await client.get(
            f"/containers/{container_id}/stats", params={"stream": "false", "one-shot": "true"},
            timeout=10,
        )
        resp.raise_for_status()
        return parse_stats(resp.json())
    except Exception as exc:
        log.warning("stats for %s failed: %s", container_id[:12], type(exc).__name__)
        return None


async def read_stats(
    socket_path: str, containers: list[ContainerState],
    transport: httpx.AsyncBaseTransport | None = None,
) -> dict[str, dict[str, Any]]:
    """Counters per running container name. `transport` is for tests."""
    running = [c for c in containers if c.state == "running" and c.id]
    transport = transport or httpx.AsyncHTTPTransport(uds=socket_path)
    gate = asyncio.Semaphore(CONCURRENCY)
    async with httpx.AsyncClient(transport=transport, base_url="http://docker") as client:

        async def one(c: ContainerState) -> tuple[str, dict[str, Any] | None]:
            async with gate:
                return c.name, await _stats(client, c.id)

        results = await asyncio.gather(*(one(c) for c in running))
    return {name: stats for name, stats in results if stats is not None}


def note_updates(store: Store, containers: list[ContainerState], now: datetime) -> list[str]:
    """Record containers whose image changed since the last check."""
    previous: dict[str, list[str]] = store.get_cache(IMAGES_KEY) or {}
    current = {c.name: [c.image, c.image_id] for c in containers if c.image_id}
    updated = []
    for name, (image, image_id) in current.items():
        before = previous.get(name)
        if before and before[1] != image_id:
            store.add_container_update(now, name, image, before[1], image_id)
            updated.append(name)
    # Keep names that are gone for now, so a container recreated a few minutes
    # later still compares against its old image.
    store.put_cache(IMAGES_KEY, {**previous, **current})
    return updated


async def collect(
    cfg: dict[str, Any], store: Store, transport: httpx.AsyncBaseTransport | None = None
) -> DockerOverview:
    socket = cfg["nas"]["docker_socket"]
    containers = await docker.list_containers(socket, transport=transport)
    if containers is None:
        raise RuntimeError("docker socket unavailable")
    now = datetime.now(UTC)

    counters = await read_stats(socket, containers, transport=transport)
    previous = store.get_cache(COUNTERS_KEY) or {}
    elapsed = (now - datetime.fromisoformat(previous["ts"])).total_seconds() if previous else 0
    store.put_cache(COUNTERS_KEY, {"ts": now.isoformat(), "containers": counters})

    rows: list[ContainerLoad] = []
    for c in containers:
        stats = counters.get(c.name)
        cpu, rx, tx = rates(stats, (previous.get("containers") or {}).get(c.name), elapsed) \
            if stats else (None, None, None)
        if stats:
            store.put_container_sample(now, c.name, cpu, stats["mem_bytes"])
        rows.append(
            ContainerLoad(
                name=c.name, project=c.project, image=c.image, state=c.state, health=c.health,
                status=c.status, cpu_pct=cpu, mem_bytes=stats["mem_bytes"] if stats else None,
                mem_limit=stats["mem_limit"] if stats else None, rx_bps=rx, tx_bps=tx,
            )
        )
    store.prune_container_samples()
    note_updates(store, containers, now)

    return DockerOverview(
        as_of=now,
        stale=False,
        containers=rows,
        cpu_pct=round(sum(r.cpu_pct or 0 for r in rows), 2),
        mem_bytes=sum(r.mem_bytes or 0 for r in rows),
    )


BUCKET_MINUTES = 10


def history(rows: list[Any], bucket_minutes: int = BUCKET_MINUTES) -> list[ContainerPoint]:
    """Average minute samples into buckets: 10 minutes gives 144 points for 24h."""
    buckets: dict[datetime, list[Any]] = {}
    for r in rows:
        t = datetime.fromisoformat(r["ts"])
        start = t.replace(minute=t.minute - t.minute % bucket_minutes, second=0, microsecond=0)
        buckets.setdefault(start, []).append(r)

    def mean(values: list[float]) -> float | None:
        return sum(values) / len(values) if values else None

    points = []
    for start, items in sorted(buckets.items()):
        cpu = mean([r["cpu_pct"] for r in items if r["cpu_pct"] is not None])
        mem = mean([r["mem_bytes"] for r in items if r["mem_bytes"] is not None])
        points.append(
            ContainerPoint(
                t=start,
                cpu=round(cpu, 2) if cpu is not None else None,
                mem=int(mem) if mem is not None else None,
            )
        )
    return points


SPARKLINE_MINUTES = 30


def sparklines(rows: list[Any]) -> dict[str, list[float | None]]:
    """CPU per container in 30-minute averages (48 points for 24h), for the
    small charts in the container list: one request instead of one per row."""
    by_name: dict[str, list[Any]] = {}
    for r in rows:
        by_name.setdefault(r["name"], []).append(r)
    return {
        name: [p.cpu for p in history(items, SPARKLINE_MINUTES)]
        for name, items in by_name.items()
    }
