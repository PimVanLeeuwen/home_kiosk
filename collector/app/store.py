"""SQLite persistence: last-good payload cache, daily snapshots, NAS samples.

Plain sqlite3, no ORM. Connections are short-lived and created per call, which
is fine at this scale and keeps the scheduler threads from sharing one.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from contextlib import AbstractContextManager, contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from .models import Service

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

-- One row per pool per day, for the "months at current rate" projection.
-- nas_sample's 24h window is far too short to fit a trend to.
CREATE TABLE IF NOT EXISTS storage_sample (
    date       TEXT NOT NULL,
    mountpoint TEXT NOT NULL,
    used_bytes INTEGER NOT NULL,
    PRIMARY KEY (date, mountpoint)
);

"""

# Home hub service catalog. Seeded from config.yaml once, then edited in the
# app. An entry is either a NAS service (port, path) or an external link (url).
SERVICE_TABLE = """
CREATE TABLE IF NOT EXISTS {name} (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    grp         TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    port        INTEGER,
    path        TEXT NOT NULL DEFAULT '/',
    url         TEXT,
    container   TEXT,
    widget      TEXT,
    icon        TEXT,
    sort        INTEGER NOT NULL
);
"""

CONTAINER_TABLES = """
-- Per-container load, one row per container per minute, 24h rolling.
CREATE TABLE IF NOT EXISTS container_sample (
    ts        TEXT NOT NULL,
    name      TEXT NOT NULL,
    cpu_pct   REAL,
    mem_bytes INTEGER,
    PRIMARY KEY (name, ts)
);

-- Image updates noticed by the Docker page (Watchtower or by hand).
CREATE TABLE IF NOT EXISTS container_update (
    ts           TEXT NOT NULL,
    name         TEXT NOT NULL,
    image        TEXT NOT NULL,
    old_image_id TEXT NOT NULL,
    new_image_id TEXT NOT NULL
);
"""

CONTAINER_SAMPLE_RETENTION = timedelta(hours=24)

SERVICE_COLUMNS = "id, name, grp, description, port, path, url, container, widget, icon, sort"

NAS_SAMPLE_RETENTION = timedelta(hours=24)


class Store:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.executescript(
                SCHEMA + SERVICE_TABLE.format(name="service") + CONTAINER_TABLES
            )
            # True when this start upgraded a catalog from before links existed.
            self.catalog_upgraded = self._add_link_support(conn)
            # True when this start added icons to an existing catalog. The links
            # rebuild above already creates the icon column, so it counts too.
            self.catalog_icons_added = (
                self._add_icon_support(conn) or self.catalog_upgraded
            )

    @staticmethod
    def _add_link_support(conn: sqlite3.Connection) -> bool:
        """Before links, `port` was NOT NULL and there was no `url`. SQLite
        cannot relax a NOT NULL in place, so the table is rebuilt."""
        columns = {r["name"] for r in conn.execute("PRAGMA table_info(service)")}
        if "url" in columns:
            return False
        old = "id, name, grp, description, port, path, container, widget, sort"
        conn.executescript(
            SERVICE_TABLE.format(name="service_new")
            + f"INSERT INTO service_new ({old}) SELECT {old} FROM service;"
            + "DROP TABLE service; ALTER TABLE service_new RENAME TO service;"
        )
        return True

    @staticmethod
    def _add_icon_support(conn: sqlite3.Connection) -> bool:
        columns = {r["name"] for r in conn.execute("PRAGMA table_info(service)")}
        if "icon" in columns:
            return False
        conn.execute("ALTER TABLE service ADD COLUMN icon TEXT")
        return True

    def connect(self) -> AbstractContextManager[sqlite3.Connection]:
        """A connection for modules that keep their own tables (app.alerts)."""
        return self._connect()

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

    # --- storage_sample: daily per-pool usage for the runway projection ------

    def put_storage_sample(self, date: str, mountpoint: str, used_bytes: int) -> None:
        """Record today's usage, overwriting any earlier reading for the day."""
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO storage_sample (date, mountpoint, used_bytes) VALUES (?, ?, ?) "
                "ON CONFLICT(date, mountpoint) DO UPDATE SET used_bytes = excluded.used_bytes",
                (date, mountpoint, used_bytes),
            )

    def storage_history(self, mountpoint: str, limit: int = 60) -> list[sqlite3.Row]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT date, used_bytes FROM storage_sample WHERE mountpoint = ? "
                "ORDER BY date DESC LIMIT ?",
                (mountpoint, limit),
            ).fetchall()
        return list(reversed(rows))

    def prune_nas_samples(self, retention: timedelta = NAS_SAMPLE_RETENTION) -> int:
        cutoff = (datetime.now(UTC) - retention).isoformat()
        with self._connect() as conn:
            cur = conn.execute("DELETE FROM nas_sample WHERE ts < ?", (cutoff,))
            return cur.rowcount

    # --- service: the Home hub catalog ---------------------------------------

    def seed_services(self, services: list[Service]) -> bool:
        """Insert the default catalog, but only into an empty table: once the
        catalog has been edited in the app, config.yaml no longer applies."""
        with self._connect() as conn:
            if conn.execute("SELECT 1 FROM service LIMIT 1").fetchone():
                return False
            conn.executemany(
                f"INSERT INTO service ({SERVICE_COLUMNS}) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                [(*self._values(s), i) for i, s in enumerate(services)],
            )
        return True

    def fill_missing_icons(self, defaults: list[Service]) -> list[str]:
        """Give entries without an icon the default icon for their id; returns
        the ids updated. Used once, when icons arrive in an existing catalog."""
        icons = {s.id: s.icon for s in defaults if s.icon}
        with self._connect() as conn:
            updated = []
            for service_id, icon in icons.items():
                cur = conn.execute(
                    "UPDATE service SET icon = ? WHERE id = ? AND icon IS NULL", (icon, service_id)
                )
                if cur.rowcount:
                    updated.append(service_id)
        return updated

    def add_missing_services(self, services: list[Service]) -> list[str]:
        """Add entries whose id is not in the catalog yet; returns their ids.
        Used once, when an upgrade brings defaults an existing catalog lacks."""
        existing = {s.id for s in self.list_services()}
        added = [s for s in services if s.id not in existing]
        for service in added:
            self.add_service(service)
        return [s.id for s in added]

    @staticmethod
    def _values(s: Service) -> tuple[Any, ...]:
        return (s.id, s.name, s.group, s.description, s.port, s.path, s.url, s.container,
                s.widget, s.icon)

    def list_services(self) -> list[Service]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM service ORDER BY sort, name").fetchall()
        return [
            Service(
                id=r["id"],
                name=r["name"],
                group=r["grp"],
                description=r["description"],
                port=r["port"],
                path=r["path"],
                url=r["url"],
                container=r["container"],
                widget=r["widget"],
                icon=r["icon"],
            )
            for r in rows
        ]

    def add_service(self, service: Service) -> None:
        """Append at the end of its group, or at the very end for a new group."""
        with self._connect() as conn:
            sort = self._sort_after_group(conn, service.group)
            conn.execute("UPDATE service SET sort = sort + 1 WHERE sort >= ?", (sort,))
            conn.execute(
                f"INSERT INTO service ({SERVICE_COLUMNS}) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (*self._values(service), sort),
            )

    def update_service(self, service: Service) -> bool:
        """Overwrite a service. Moving it to another group puts it at the end
        of that group, so groups stay contiguous."""
        with self._connect() as conn:
            row = conn.execute("SELECT grp FROM service WHERE id = ?", (service.id,)).fetchone()
            if row is None:
                return False
            conn.execute(
                "UPDATE service SET name = ?, grp = ?, description = ?, port = ?, path = ?, "
                "url = ?, container = ?, widget = ?, icon = ? WHERE id = ?",
                (*self._values(service)[1:], service.id),
            )
            if row["grp"] != service.group:
                # Last in the stored order, so normalising puts it at the end
                # of its new group.
                conn.execute(
                    "UPDATE service SET sort = (SELECT MAX(sort) + 1 FROM service) WHERE id = ?",
                    (service.id,),
                )
                self._keep_groups_together(conn)
        return True

    def delete_service(self, service_id: str) -> bool:
        with self._connect() as conn:
            cur = conn.execute("DELETE FROM service WHERE id = ?", (service_id,))
            return cur.rowcount > 0

    def reorder_services(self, ids: list[str]) -> None:
        with self._connect() as conn:
            self._write_order(conn, ids)
            self._keep_groups_together(conn)

    def rename_group(self, old: str, new: str) -> bool:
        with self._connect() as conn:
            cur = conn.execute("UPDATE service SET grp = ? WHERE grp = ?", (new, old))
            # Renaming onto an existing group merges the two.
            self._keep_groups_together(conn)
            return cur.rowcount > 0

    @classmethod
    def _keep_groups_together(cls, conn: sqlite3.Connection) -> None:
        """Make every group contiguous, groups in order of their first service
        and services in their existing order within a group."""
        rows = conn.execute("SELECT id, grp FROM service ORDER BY sort, name").fetchall()
        by_group: dict[str, list[str]] = {}
        for r in rows:
            by_group.setdefault(r["grp"], []).append(r["id"])
        cls._write_order(conn, [sid for ids in by_group.values() for sid in ids])

    @staticmethod
    def _write_order(conn: sqlite3.Connection, ids: list[str]) -> None:
        conn.executemany("UPDATE service SET sort = ? WHERE id = ?", list(enumerate(ids)))

    @staticmethod
    def _sort_after_group(conn: sqlite3.Connection, group: str) -> int:
        row = conn.execute("SELECT MAX(sort) AS m FROM service WHERE grp = ?", (group,)).fetchone()
        if row["m"] is not None:
            return row["m"] + 1
        row = conn.execute("SELECT MAX(sort) AS m FROM service").fetchone()
        return (row["m"] + 1) if row["m"] is not None else 0

    # --- container_sample / container_update: the Docker page ----------------

    def put_container_sample(
        self, ts: datetime, name: str, cpu_pct: float | None, mem_bytes: int | None
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO container_sample (ts, name, cpu_pct, mem_bytes) VALUES (?, ?, ?, ?) "
                "ON CONFLICT(name, ts) DO NOTHING",
                (ts.isoformat(), name, cpu_pct, mem_bytes),
            )

    def container_samples(self, name: str, since: datetime) -> list[sqlite3.Row]:
        with self._connect() as conn:
            return list(conn.execute(
                "SELECT ts, cpu_pct, mem_bytes FROM container_sample "
                "WHERE name = ? AND ts >= ? ORDER BY ts",
                (name, since.isoformat()),
            ))

    def all_container_samples(self, since: datetime) -> list[sqlite3.Row]:
        with self._connect() as conn:
            return list(conn.execute(
                "SELECT ts, name, cpu_pct, mem_bytes FROM container_sample WHERE ts >= ? "
                "ORDER BY name, ts",
                (since.isoformat(),),
            ))

    def prune_container_samples(self, retention: timedelta = CONTAINER_SAMPLE_RETENTION) -> int:
        cutoff = (datetime.now(UTC) - retention).isoformat()
        with self._connect() as conn:
            return conn.execute("DELETE FROM container_sample WHERE ts < ?", (cutoff,)).rowcount

    def add_container_update(
        self, ts: datetime, name: str, image: str, old_image_id: str, new_image_id: str
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO container_update (ts, name, image, old_image_id, new_image_id) "
                "VALUES (?, ?, ?, ?, ?)",
                (ts.isoformat(), name, image, old_image_id, new_image_id),
            )

    def container_updates(self, limit: int = 100) -> list[sqlite3.Row]:
        with self._connect() as conn:
            return list(conn.execute(
                "SELECT * FROM container_update ORDER BY ts DESC LIMIT ?", (limit,)
            ))
