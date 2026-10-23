"""Asking the NAS for a restore check now (decided 2026-10-23, from the hub's Backups page
only). The hub cannot run it: no container gets Docker access (decided 2026-10-09). It
writes a request file into its own data folder; a cron line on the NAS host
(nas-docker `host-jobs/restore-check-on-request.sh`, every 5 minutes) renames it to
`.running`, runs `restore-check.sh` and removes it. The result is the usual run record.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Literal

REQUEST = "restore-check.request"
RUNNING = "restore-check.running"
SPACING = timedelta(hours=1)  # at most one check an hour, asked or not

State = Literal["idle", "requested", "running"]


class NotNow(Exception):
    """A check is already asked for or running, or one ran within the hour."""


def _since(path: Path) -> str | None:
    try:
        text = path.read_text().strip()
        return datetime.fromisoformat(text).isoformat() if text else None
    except (OSError, ValueError):
        return None


def state(folder: Path) -> dict[str, Any]:
    """{"state": "idle" | "requested" | "running", "since": when it was asked, or None}."""
    for name, word in ((RUNNING, "running"), (REQUEST, "requested")):
        if (folder / name).exists():
            return {"state": word, "since": _since(folder / name)}
    return {"state": "idle", "since": None}


def request(folder: Path, checks: list[dict[str, Any]], now: datetime) -> dict[str, Any]:
    """Leaves the request for the NAS; NotNow while one is pending or within the hour."""
    if state(folder)["state"] != "idle":
        raise NotNow("A restore check is already asked for or running.")
    started = [datetime.fromisoformat(c["started"]) for c in checks if c.get("started")]
    if started and now - max(started) < SPACING:
        raise NotNow("A restore check ran less than an hour ago.")
    (folder / REQUEST).write_text(now.isoformat())
    return state(folder)
