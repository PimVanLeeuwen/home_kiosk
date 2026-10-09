"""Nightly consistent copy of the hub's own SQLite database, for the backup.

The 03:00 rclone run copies /volume1/docker file by file, so it can catch the
live database half way through a write. `VACUUM INTO` writes a complete copy
from one read transaction instead, into `backup/` next to the database, and
the sync takes that along. The copy is written under a temporary name and
then renamed, so the sync never sees a half-written file.
"""

from __future__ import annotations

import asyncio
import logging
import sqlite3
from contextlib import suppress
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ..models import DatabaseCopy
from ..store import Store

log = logging.getLogger(__name__)

CACHE_KEY = "db_copy"


def settings(cfg: dict[str, Any]) -> dict[str, Any]:
    copy = cfg.get("database_copy") or {}
    return {"at": str(copy.get("at", "02:45"))}


def target(store: Store) -> Path:
    return store.path.parent / "backup" / store.path.name


def write(store: Store) -> DatabaseCopy:
    dest = target(store)
    partial = dest.with_name(dest.name + ".partial")
    try:
        dest.parent.mkdir(parents=True, exist_ok=True)
        partial.unlink(missing_ok=True)  # VACUUM INTO refuses an existing file
        conn = sqlite3.connect(store.path, timeout=30)
        try:
            conn.execute("VACUUM INTO ?", (str(partial),))
        finally:
            conn.close()
        partial.replace(dest)
        return DatabaseCopy(as_of=datetime.now(UTC), ok=True, path=str(dest),
                            bytes=dest.stat().st_size)
    except (OSError, sqlite3.Error) as exc:
        log.exception("copying the hub database failed")
        with suppress(OSError):
            partial.unlink(missing_ok=True)
        return DatabaseCopy(as_of=datetime.now(UTC), ok=False, path=str(dest),
                            error=str(exc)[:300])


async def collect(store: Store) -> DatabaseCopy:
    result = await asyncio.to_thread(write, store)
    if result.ok:
        result.last_success = result.as_of
    else:
        previous = (store.get_cache(CACHE_KEY) or {}).get("last_success")
        result.last_success = datetime.fromisoformat(previous) if previous else None
    return result
