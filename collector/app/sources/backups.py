"""Backup run history for the Backups page.

rclone's backup.sh (nas-docker) appends one JSON line per run to
backup-runs.jsonl next to the status marker; the collector reads it from the
same read-only mount. Records start with the backup.sh that writes them, so
there is no history from before that.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime, time, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from ..models import BackupHistory, BackupRun, BackupVolume, VolumeSummary

log = logging.getLogger(__name__)

MAX_RUNS = 90


def parse_volume(raw: dict[str, Any]) -> BackupVolume:
    stats = (raw.get("rclone") or {}).get("stats") or {}
    exit_code = int(raw.get("exit", 1))
    # rclone keeps the last error even when a retry fixed it: only show it when
    # the volume actually failed or counted errors.
    failed = exit_code != 0 or (stats.get("errors") or 0) > 0
    last_error = stats.get("lastError") if failed else None
    return BackupVolume(
        name=str(raw["name"]),
        ok=exit_code == 0,
        exit_code=exit_code,
        seconds=int(raw.get("seconds", 0)),
        bytes=stats.get("bytes"),
        transfers=stats.get("transfers"),
        checks=stats.get("checks"),
        deletes=stats.get("deletes"),
        errors=stats.get("errors"),
        last_error=str(last_error)[:300] if last_error else None,
    )


def parse_line(line: str) -> BackupRun | None:
    """One run record, or None for a line that is not one (half-written, edited)."""
    try:
        raw = json.loads(line)
        return BackupRun(
            started=raw["started"],
            finished=raw["finished"],
            ok=bool(raw["ok"]),
            volumes=[parse_volume(v) for v in raw.get("volumes", [])],
        )
    except Exception:
        return None


def summarise(runs: list[BackupRun]) -> list[VolumeSummary]:
    """Per volume: its newest run and the last time it succeeded. `runs` newest first."""
    names: list[str] = []
    for run in runs:
        for volume in run.volumes:
            if volume.name not in names:
                names.append(volume.name)
    summaries = []
    for name in sorted(names):
        with_volume = [r for r in runs if any(v.name == name for v in r.volumes)]
        success = next(
            (r for r in with_volume if any(v.name == name and v.ok for v in r.volumes)), None
        )
        summaries.append(
            VolumeSummary(
                name=name,
                last_run=with_volume[0] if with_volume else None,
                last_success=success.finished if success else None,
            )
        )
    return summaries


def next_run(after: datetime, at: str, tz: str) -> datetime:
    """The next HH:MM (local time in `tz`) strictly after `after`, matching
    schedule.sh in nas-docker, which starts backup.sh nightly at BACKUP_AT."""
    zone = ZoneInfo(tz)
    hour, minute = (int(part) for part in at.split(":"))
    local = after.astimezone(zone)
    candidate = datetime.combine(local.date(), time(hour, minute), tzinfo=zone)
    if candidate <= local:
        candidate = datetime.combine(local.date() + timedelta(days=1), time(hour, minute),
                                     tzinfo=zone)
    return candidate


def read(path: str, at: str = "03:00", tz: str = "UTC") -> BackupHistory:
    file = Path(path)
    lines = file.read_text(errors="replace").splitlines() if file.exists() else []
    runs = [run for line in lines if line.strip() and (run := parse_line(line))]
    skipped = sum(1 for line in lines if line.strip()) - len(runs)
    if skipped:
        log.warning("skipped %d unreadable backup run lines", skipped)
    runs.sort(key=lambda r: r.started, reverse=True)
    runs = runs[:MAX_RUNS]
    return BackupHistory(
        as_of=datetime.now(UTC),
        stale=False,
        runs=runs,
        volumes=summarise(runs),
        next_due=next_run(runs[0].finished, at, tz) if runs else None,
    )


async def collect(cfg: dict[str, Any]) -> BackupHistory:
    return read(
        cfg["nas"]["backup_runs"],
        at=cfg["nas"].get("backup_at", "03:00"),
        tz=cfg.get("timezone", "UTC"),
    )
