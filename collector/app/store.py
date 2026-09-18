"""SQLite persistence: last-good payload cache, daily snapshots, NAS samples.

Plain sqlite3, no ORM. Connections are short-lived and created per call, which
is fine at this scale and keeps the scheduler threads from sharing one.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

SCHEMA = """
CREATE TABLE IF NOT EXISTS portfolio_snapshot (
    date        TEXT PRIMARY KEY,
    total_value REAL NOT NULL,
    currency    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS nas_sample (
    ts       TEXT PRIMARY KEY,
    rx_bytes INTEGER,
    tx_bytes INTEGER,
    cpu_pct  REAL,
    ram_pct  REAL,
    cpu_temp REAL
);

CREATE TABLE IF NOT EXISTS cache (
    key          TEXT PRIMARY KEY,
    payload_json TEXT NOT NULL,
    fetched_at   TEXT NOT NULL
);
"""

NAS_SAMPLE_RETENTION = timedelta(hours=24)


class Store:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.executescript(SCHEMA)

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.path, timeout=10)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    # --- cache: last-good response per endpoint ------------------------------

    def put_cache(self, key: str, payload: dict[str, Any]) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO cache (key, payload_json, fetched_at) VALUES (?, ?, ?) "
                "ON CONFLICT(key) DO UPDATE SET payload_json = excluded.payload_json, "
                "fetched_at = excluded.fetched_at",
                (key, json.dumps(payload), datetime.now(UTC).isoformat()),
            )

    def get_cache(self, key: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT payload_json FROM cache WHERE key = ?", (key,)
            ).fetchone()
        return json.loads(row["payload_json"]) if row else None

    # --- portfolio_snapshot: daily rows for the 30-point chart ---------------

    def put_snapshot(self, date: str, total_value: float, currency: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO portfolio_snapshot (date, total_value, currency) VALUES (?, ?, ?) "
                "ON CONFLICT(date) DO UPDATE SET total_value = excluded.total_value, "
                "currency = excluded.currency",
                (date, total_value, currency),
            )

    def recent_snapshots(self, limit: int = 30) -> list[sqlite3.Row]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT date, total_value, currency FROM portfolio_snapshot "
                "ORDER BY date DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return list(reversed(rows))

    # --- nas_sample: 24h rolling window --------------------------------------

    def put_nas_sample(
        self,
        ts: datetime,
        rx_bytes: int | None,
        tx_bytes: int | None,
        cpu_pct: float | None,
        ram_pct: float | None,
        cpu_temp: float | None,
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO nas_sample (ts, rx_bytes, tx_bytes, cpu_pct, ram_pct, cpu_temp) "
                "VALUES (?, ?, ?, ?, ?, ?) ON CONFLICT(ts) DO NOTHING",
                (ts.isoformat(), rx_bytes, tx_bytes, cpu_pct, ram_pct, cpu_temp),
            )

    def recent_nas_samples(self, since: datetime) -> list[sqlite3.Row]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM nas_sample WHERE ts >= ? ORDER BY ts", (since.isoformat(),)
            ).fetchall()
        return list(rows)

    def prune_nas_samples(self, retention: timedelta = NAS_SAMPLE_RETENTION) -> int:
        cutoff = (datetime.now(UTC) - retention).isoformat()
        with self._connect() as conn:
            cur = conn.execute("DELETE FROM nas_sample WHERE ts < ?", (cutoff,))
            return cur.rowcount
