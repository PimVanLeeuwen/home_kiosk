"""Backups other machines push to this NAS, for the Backups page and the backup alert.

Another NAS's Hyper Backup writes into a folder here (over WebDAV, through
Tailscale), and the collector reads that folder through a read-only mount. It
writes no run record we could read, so a backup is judged by its files: the
newest modification anywhere in the folder is when the last one arrived, and a
night with any change in it counts as a night with a backup.
"""

from __future__ import annotations

import asyncio
import os
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from .. import config
from ..models import BackupNight, IncomingBackup, IncomingBackups

CACHE_KEY = "incoming_backups"
NIGHTS = 14
# A night runs from noon to noon, so a run that starts late and ends after
# midnight still counts once, for the evening it started.
NOON = time(12, 0)


def night_of(moment: datetime, zone: ZoneInfo) -> date:
    local = moment.astimezone(zone)
    return local.date() if local.time() >= NOON else local.date() - timedelta(days=1)


def scan(path: str) -> tuple[float, float, int, int, set[float]]:
    """Walk the folder: (newest mtime, oldest mtime, bytes, files, every mtime).

    Raises OSError when the folder itself cannot be read. Folders count too: Hyper
    Backup removes old chunks as well as adding new ones.
    """
    root = Path(path)
    newest = oldest = root.stat().st_mtime
    os.listdir(root)  # unreadable (wrong owner, missing mount): fail here, not silently empty
    size = files = 0
    stamps: set[float] = set()
    for folder, dirs, names in os.walk(root):
        for name, is_file in [(d, False) for d in dirs] + [(n, True) for n in names]:
            try:
                info = os.lstat(os.path.join(folder, name))
            except OSError:
                continue  # removed while walking
            stamps.add(info.st_mtime)
            newest, oldest = max(newest, info.st_mtime), min(oldest, info.st_mtime)
            if is_file:
                size += info.st_size
                files += 1
    return newest, oldest, size, files, stamps


def nights(stamps: set[float], oldest: float, now: datetime, zone: ZoneInfo) -> list[BackupNight]:
    """The last NIGHTS nights, newest first, from the first one the folder existed.
    Tonight only once something arrived: until then it is not late."""
    changed = {night_of(datetime.fromtimestamp(s, UTC), zone) for s in stamps}
    tonight = night_of(now, zone)
    first = night_of(datetime.fromtimestamp(oldest, UTC), zone)
    shown = []
    for back in range(NIGHTS):
        night = tonight - timedelta(days=back)
        if night < first:
            break
        if night == tonight and night not in changed:
            continue
        shown.append(BackupNight(night=night, ok=night in changed))
    return shown


def read(source: dict[str, Any], now: datetime, zone: ZoneInfo) -> IncomingBackup:
    base = {"name": source["name"], "label": source.get("label") or source["name"],
            "max_days": int(source.get("max_days", 3)), "at": source.get("at")}
    try:
        newest, oldest, size, files, stamps = scan(source["path"])
    except OSError as exc:
        # The class and errno only: the message carries the path.
        return IncomingBackup(**base, present=False,
                              error=f"{type(exc).__name__} {exc.errno or ''}".strip())
    return IncomingBackup(
        **base, present=True, last_change=datetime.fromtimestamp(newest, UTC), bytes=size,
        files=files, nights=nights(stamps, oldest, now, zone))


def _collect(cfg: dict[str, Any]) -> IncomingBackups:
    now = datetime.now(UTC)
    zone = config.zone(cfg)
    return IncomingBackups(as_of=now, sources=[read(s, now, zone)
                                               for s in cfg.get("incoming_backups") or []])


async def collect(cfg: dict[str, Any]) -> IncomingBackups:
    # A walk over a few thousand Hyper Backup chunks: keep it off the event loop.
    return await asyncio.to_thread(_collect, cfg)
