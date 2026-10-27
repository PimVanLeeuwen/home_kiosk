"""Database dumps for the Backups page: the host job's and the hub's own copy.

The Postgres databases are dumped at 02:30 by nas-docker's
host-jobs/dump-databases.sh (root's crontab on the NAS), which appends one JSON
line per run to dump-runs.jsonl next to the dumps in /volume3/backups/databases.
The collector reads it through a read-only mount. The hub's own SQLite copy is
made by the collector itself (db_copy, 02:45). The monthly restore check
(host-jobs/restore-check.sh) writes restore-checks.jsonl in the same folder.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ..models import DatabaseDumps, DumpedDatabase, DumpRun, RestoreCheck
from ..store import Store
from . import db_copy

log = logging.getLogger(__name__)

CACHE_KEY = "dumps"
MAX_RUNS = 30
MAX_RESTORE_CHECKS = 12  # a year of monthly checks
LABELS = {"hub": "Home hub"}


def label(name: str) -> str:
    return LABELS.get(name, name.capitalize())


def parse_line(line: str) -> dict[str, Any] | None:
    """One run record, or None for a line that is not one (half-written, edited)."""
    try:
        raw = json.loads(line)
        return {
            "started": datetime.fromisoformat(raw["started"]),
            "finished": datetime.fromisoformat(raw["finished"]),
            "ok": bool(raw["ok"]),
            "dumps": [
                {"name": str(d["name"]), "ok": bool(d["ok"]), "bytes": int(d.get("bytes") or 0),
                 "error": str(d["error"])[:300] if d.get("error") else None}
                for d in raw.get("dumps", [])
            ],
        }
    except Exception:
        return None


def read_runs(path: str) -> list[dict[str, Any]]:
    """The host job's runs, newest first."""
    file = Path(path)
    lines = [line for line in file.read_text(errors="replace").splitlines() if line.strip()] \
        if file.exists() else []
    runs = [run for line in lines if (run := parse_line(line))]
    if len(runs) < len(lines):
        log.warning("skipped %d unreadable dump run lines", len(lines) - len(runs))
    return sorted(runs, key=lambda r: r["finished"], reverse=True)


def read_restore_checks(path: str) -> list[RestoreCheck]:
    """The monthly restore check's runs, newest first. Unreadable lines are skipped."""
    file = Path(path)
    checks = []
    for line in file.read_text(errors="replace").splitlines() if file.exists() else []:
        if not line.strip():
            continue
        try:
            checks.append(RestoreCheck.model_validate_json(line))
        except ValueError:
            log.warning("skipped an unreadable restore check line")
    return sorted(checks, key=lambda c: c.finished, reverse=True)


def summarise(runs: list[dict[str, Any]]) -> list[DumpedDatabase]:
    """Per database: its newest attempt and the last time it succeeded. Only the databases the
    newest run dumped: the job writes an entry for every one it tries, so one that is missing
    there was taken out of the job (Tandoor, 2026-10-27) and must not turn into an alert."""
    names = [d["name"] for d in runs[0]["dumps"]] if runs else []
    databases = []
    for name in sorted(names):
        attempts = [(run["finished"], d) for run in runs for d in run["dumps"] if d["name"] == name]
        at, newest = attempts[0]
        success = next((when for when, d in attempts if d["ok"]), None)
        databases.append(DumpedDatabase(
            name=name, label=label(name), kind="pg_dump", ok=newest["ok"], at=at,
            bytes=newest["bytes"] if newest["ok"] else None, error=newest["error"],
            last_success=success))
    return databases


def hub_copy(store: Store) -> DumpedDatabase:
    copy = store.get_cache(db_copy.CACHE_KEY)
    if copy is None:
        return DumpedDatabase(name="hub", label=label("hub"), kind="sqlite", ok=None)
    return DumpedDatabase(
        name="hub", label=label("hub"), kind="sqlite", ok=copy["ok"], at=copy["as_of"],
        bytes=copy.get("bytes"), error=copy.get("error"), last_success=copy.get("last_success"))


def read(path: str, store: Store, restore_path: str | None = None) -> DatabaseDumps:
    runs = read_runs(path)
    checks = read_restore_checks(restore_path) if restore_path else []
    return DatabaseDumps(
        as_of=datetime.now(UTC),
        databases=[*summarise(runs), hub_copy(store)],
        runs=[DumpRun(started=r["started"], finished=r["finished"], ok=r["ok"],
                      failed=sum(1 for d in r["dumps"] if not d["ok"]))
              for r in runs[:MAX_RUNS]],
        restore_checks=checks[:MAX_RESTORE_CHECKS],
        last_verified=next((c.finished for c in checks if c.ok), None),
    )


async def collect(cfg: dict[str, Any], store: Store) -> DatabaseDumps:
    nas = cfg["nas"]
    return read(nas.get("dump_runs", "/backups/databases/dump-runs.jsonl"), store,
                nas.get("restore_checks", "/backups/databases/restore-checks.jsonl"))
