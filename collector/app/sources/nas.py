"""Builds /api/nas from node_exporter, Scrutiny, the Docker socket and the
rclone backup marker.

Counter-based figures (CPU busy percentage, network throughput) need two
readings to produce a rate, so the previous raw counters are kept in the cache
table under `nas_counters`. That survives a restart, unlike an in-memory value.
"""

from __future__ import annotations

import logging
import math
import re
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx

from ..models import Backup, Containers, Disk, Nas, Network, NetworkPoint, Pool, Storage
from ..store import Store
from . import docker

log = logging.getLogger(__name__)

COUNTER_KEY = "nas_counters"

_SAMPLE = re.compile(
    r"^(?P<name>[a-zA-Z_:][\w:]*)(?:\{(?P<labels>[^}]*)\})?\s+(?P<value>\S+)$"
)
_LABEL = re.compile(r'(\w+)="((?:[^"\\]|\\.)*)"')


def parse_metrics(text: str) -> dict[str, list[tuple[dict[str, str], float]]]:
    """Parse the Prometheus text exposition format into {name: [(labels, value)]}."""
    out: dict[str, list[tuple[dict[str, str], float]]] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        m = _SAMPLE.match(line)
        if not m:
            continue
        try:
            value = float(m.group("value"))
        except ValueError:
            continue
        # float() accepts "NaN" and "+Inf", and either would end up in the cached
        # JSON as a bare NaN/Infinity token that browsers refuse to parse.
        if not math.isfinite(value):
            continue
        labels = dict(_LABEL.findall(m.group("labels") or ""))
        out.setdefault(m.group("name"), []).append((labels, value))
    return out


def _first(
    metrics: dict[str, list[tuple[dict[str, str], float]]], name: str, **match: str
) -> float | None:
    for labels, value in metrics.get(name, []):
        if all(labels.get(k) == v for k, v in match.items()):
            return value
    return None


def _cpu_totals(metrics: dict[str, list[tuple[dict[str, str], float]]]) -> tuple[float, float]:
    """Return (idle_seconds, total_seconds) summed across every core."""
    idle = total = 0.0
    for labels, value in metrics.get("node_cpu_seconds_total", []):
        total += value
        if labels.get("mode") == "idle":
            idle += value
    return idle, total


def _cpu_temp(metrics: dict[str, list[tuple[dict[str, str], float]]]) -> float | None:
    """Package temperature, falling back to the hottest core."""
    labels_by_sensor = {
        (lbl.get("chip"), lbl.get("sensor")): lbl.get("label")
        for lbl, _ in metrics.get("node_hwmon_sensor_label", [])
    }
    cores: list[float] = []
    for lbl, value in metrics.get("node_hwmon_temp_celsius", []):
        name = labels_by_sensor.get((lbl.get("chip"), lbl.get("sensor"))) or ""
        if name.startswith("Package id"):
            return value
        if name.startswith("Core "):
            cores.append(value)
    return max(cores) if cores else None


MIN_PROJECTION_DAYS = 7
DAYS_PER_MONTH = 30.44


def _projection_months(rows: list[Any], free_bytes: float) -> float | None:
    """Months until full at the mean daily growth rate.

    Returns None when there is too little history to mean anything, or when
    usage is flat or shrinking — in which case there is no runway to report and
    the view hides the line rather than printing an implausible number.
    """
    if len(rows) < MIN_PROJECTION_DAYS:
        return None
    first, last = rows[0], rows[-1]
    span_days = (date.fromisoformat(last["date"]) - date.fromisoformat(first["date"])).days
    if span_days < MIN_PROJECTION_DAYS:
        return None
    growth_per_day = (last["used_bytes"] - first["used_bytes"]) / span_days
    if growth_per_day <= 0:
        return None
    return round(free_bytes / growth_per_day / DAYS_PER_MONTH, 1)


def _storage(
    metrics: dict[str, list[tuple[dict[str, str], float]]],
    mountpoints: list[str],
    store: Store,
    today: str,
) -> Storage:
    total = avail = 0.0
    pools: list[Pool] = []

    for mp in mountpoints:
        size = _first(metrics, "node_filesystem_size_bytes", mountpoint=mp)
        free = _first(metrics, "node_filesystem_avail_bytes", mountpoint=mp)
        if size is None or free is None:
            log.warning("mountpoint %s missing from node_exporter", mp)
            continue
        used = size - free
        total += size
        avail += free

        store.put_storage_sample(today, mp, int(used))
        pools.append(
            Pool(
                name=mp.lstrip("/"),
                used_bytes=int(used),
                total_bytes=int(size),
                used_pct=round(used / size * 100, 1) if size else 0.0,
                free_bytes=int(free),
                projection_months=_projection_months(store.storage_history(mp), free),
            )
        )

    # Fullest pool first: the one at risk should lead, not the biggest.
    pools.sort(key=lambda p: p.used_pct, reverse=True)

    used_total = total - avail
    return Storage(
        used_bytes=int(used_total),
        total_bytes=int(total),
        used_pct=round(used_total / total * 100, 1) if total else 0.0,
        free_bytes=int(avail),
        pools=pools,
        projection_months=None,  # per-pool is the meaningful figure; see Pool
    )


async def _disks(client: httpx.AsyncClient, base_url: str) -> list[Disk]:
    """Disk temps and SMART verdicts from Scrutiny's summary API."""
    try:
        resp = await client.get(f"{base_url.rstrip('/')}/api/summary", timeout=8)
        resp.raise_for_status()
        summary = resp.json()["data"]["summary"]
    except Exception as exc:
        log.warning("scrutiny unreachable: %s", exc)
        return []

    disks: list[Disk] = []
    for entry in summary.values():
        device = entry.get("device", {})
        status = device.get("device_status") or 0
        # Scrutiny bitfield: 0 passed, bit 0 a real SMART failure, bit 1 a
        # Scrutiny-threshold warning.
        smart = "ok" if status == 0 else ("fail" if status & 1 else "warn")
        disks.append(
            Disk(
                name=device.get("device_name", "?"),
                temp_c=(entry.get("smart") or {}).get("temp"),
                smart=smart,
            )
        )
    disks.sort(key=lambda d: d.name)
    return disks


async def _containers(socket_path: str) -> Containers:
    """Running/total container counts over the Docker UDS.

    Unavailable when the collector runs off-NAS; reported as 0/0 rather than
    failing the whole payload.
    """
    containers = await docker.list_containers(socket_path)
    if containers is None:
        return Containers(running=0, total=0)
    return Containers(
        running=sum(1 for c in containers if c.state == "running"), total=len(containers)
    )


def _backup(marker_path: str) -> Backup:
    """Read the `ok|fail <iso8601>` line written by rclone's backup.sh."""
    path = Path(marker_path)
    if not path.exists():
        return Backup(status="unknown", at=None)
    try:
        status, _, stamp = path.read_text().strip().partition(" ")
        return Backup(
            status=status if status in ("ok", "fail") else "unknown",
            at=datetime.fromisoformat(stamp) if stamp else None,
        )
    except Exception as exc:
        log.warning("backup marker unreadable: %s", exc)
        return Backup(status="unknown", at=None)


HISTORY_POINTS = 144  # 24h in 10-minute buckets — more than a 592px sparkline resolves


def _downsample(points: list[NetworkPoint], target: int = HISTORY_POINTS) -> list[NetworkPoint]:
    """Average into at most `target` buckets.

    A 60s cadence over 24h is 1440 points, roughly 100 KB of JSON per poll for a
    sparkline barely 600px wide. Averaging rather than picking every Nth point
    keeps brief spikes visible instead of dropping them between samples.
    """
    if len(points) <= target:
        return points
    size = len(points) / target
    out: list[NetworkPoint] = []
    for i in range(target):
        bucket = points[int(i * size) : max(int((i + 1) * size), int(i * size) + 1)]
        if not bucket:
            continue
        out.append(
            NetworkPoint(
                t=bucket[-1].t,
                rx=round(sum(p.rx for p in bucket) / len(bucket), 2),
                tx=round(sum(p.tx for p in bucket) / len(bucket), 2),
            )
        )
    return out


def _network_history(rows: list[Any]) -> list[NetworkPoint]:
    """Turn the stored cumulative byte counters into per-interval throughput.

    nas_sample holds raw counters, so a point is only meaningful as the delta
    against the sample before it. Counter resets (reboot, interface bounce) show
    as negatives and are dropped rather than plotted as spikes.
    """
    points: list[NetworkPoint] = []
    for previous, current in zip(rows, rows[1:], strict=False):
        elapsed = (
            datetime.fromisoformat(current["ts"]) - datetime.fromisoformat(previous["ts"])
        ).total_seconds()
        if elapsed <= 0:
            continue
        rx_delta = (current["rx_bytes"] or 0) - (previous["rx_bytes"] or 0)
        tx_delta = (current["tx_bytes"] or 0) - (previous["tx_bytes"] or 0)
        if rx_delta < 0 or tx_delta < 0:
            continue
        points.append(
            NetworkPoint(
                t=datetime.fromisoformat(current["ts"]),
                rx=round(rx_delta * 8 / 1e6 / elapsed, 2),
                tx=round(tx_delta * 8 / 1e6 / elapsed, 2),
            )
        )
    return _downsample(points)


async def collect(cfg: dict[str, Any], store: Store) -> Nas:
    nas_cfg = cfg["nas"]
    now = datetime.now(UTC)

    async with httpx.AsyncClient() as client:
        resp = await client.get(nas_cfg["node_exporter"], timeout=10)
        resp.raise_for_status()
        metrics = parse_metrics(resp.text)
        disks = await _disks(client, nas_cfg["scrutiny"])

    boot = _first(metrics, "node_boot_time_seconds") or 0.0
    mem_total = _first(metrics, "node_memory_MemTotal_bytes") or 0.0
    mem_avail = _first(metrics, "node_memory_MemAvailable_bytes") or 0.0
    iface = nas_cfg.get("network_interface", "eth0")
    rx = _first(metrics, "node_network_receive_bytes_total", device=iface) or 0.0
    tx = _first(metrics, "node_network_transmit_bytes_total", device=iface) or 0.0
    idle, total = _cpu_totals(metrics)

    # Rates need the previous reading; on the very first poll there is none.
    previous = store.get_cache(COUNTER_KEY)
    cpu_pct, rx_mbps, tx_mbps = 0.0, 0.0, 0.0
    if previous:
        elapsed = (now - datetime.fromisoformat(previous["ts"])).total_seconds()
        if elapsed > 0:
            total_delta = total - previous["cpu_total"]
            if total_delta > 0:
                idle_delta = idle - previous["cpu_idle"]
                cpu_pct = round(max(0.0, min(100.0, (1 - idle_delta / total_delta) * 100)), 1)
            rx_mbps = round(max(0.0, (rx - previous["rx"]) * 8 / 1e6 / elapsed), 2)
            tx_mbps = round(max(0.0, (tx - previous["tx"]) * 8 / 1e6 / elapsed), 2)

    store.put_cache(
        COUNTER_KEY,
        {"ts": now.isoformat(), "cpu_idle": idle, "cpu_total": total, "rx": rx, "tx": tx},
    )

    ram_pct = round((1 - mem_avail / mem_total) * 100, 1) if mem_total else 0.0
    cpu_temp = _cpu_temp(metrics)

    store.put_nas_sample(now, int(rx), int(tx), cpu_pct, ram_pct, cpu_temp)
    store.prune_nas_samples()

    history = _network_history(store.recent_nas_samples(now - timedelta(hours=24)))

    uname = next(iter(metrics.get("node_uname_info", [])), ({}, 0.0))[0]

    return Nas(
        as_of=now,
        stale=False,
        host=uname.get("nodename", "nas"),
        uptime_seconds=int(now.timestamp() - boot) if boot else 0,
        storage=_storage(metrics, nas_cfg["storage_mountpoints"], store, now.date().isoformat()),
        cpu_pct=cpu_pct,
        ram_pct=ram_pct,
        cpu_temp_c=cpu_temp,
        containers=await _containers(nas_cfg["docker_socket"]),
        disks=disks,
        network=Network(rx_mbps=rx_mbps, tx_mbps=tx_mbps, history=history),
        backup=_backup(nas_cfg["backup_marker"]),
    )
