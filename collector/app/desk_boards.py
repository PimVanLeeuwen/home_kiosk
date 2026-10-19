"""Which board is which desk panel (plan.md M16).

Every board runs the same firmware and only knows its own MAC address (the one
written on its back). It asks `/api/desk/board/<mac>`; the hub notes when it
was last seen and with which firmware, and answers with the screens of the
panel it is assigned to in Settings → Desk panels. Each panel has at most one
board: assigning a panel takes it from the board that had it.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel

from .store import Store

Panel = Literal["now", "home", "house", "test"]
MAC = re.compile(r"^[0-9a-f]{2}(:[0-9a-f]{2}){5}$")

TABLES = """
CREATE TABLE IF NOT EXISTS desk_board (
    mac        TEXT PRIMARY KEY,  -- e8:f6:0a:e4:42:b0
    panel      TEXT,              -- now, home, house, test; NULL until assigned
    first_seen TEXT NOT NULL,
    last_seen  TEXT NOT NULL,
    firmware   TEXT NOT NULL DEFAULT ''
);
"""


class Board(BaseModel):
    mac: str
    panel: Panel | None
    first_seen: datetime
    last_seen: datetime
    firmware: str


def ensure_tables(store: Store) -> None:
    with store.connect() as conn:
        conn.executescript(TABLES)


def check_in(store: Store, mac: str, firmware: str, now: datetime | None = None) -> Panel | None:
    """Notes the board's visit and returns its panel, if it has one."""
    at = (now or datetime.now(UTC)).isoformat()
    with store.connect() as conn:
        conn.execute(
            "INSERT INTO desk_board (mac, first_seen, last_seen, firmware) VALUES (?, ?, ?, ?)"
            " ON CONFLICT (mac) DO UPDATE SET last_seen = excluded.last_seen,"
            " firmware = excluded.firmware",
            (mac, at, at, firmware[:40]))
        row = conn.execute("SELECT panel FROM desk_board WHERE mac = ?", (mac,)).fetchone()
    return row["panel"]


def boards(store: Store) -> list[Board]:
    with store.connect() as conn:
        rows = conn.execute("SELECT * FROM desk_board ORDER BY first_seen, mac").fetchall()
    return [Board(**dict(r)) for r in rows]


def assign(store: Store, mac: str, panel: Panel | None) -> bool:
    """Gives the board a panel (or none); False when the hub has never seen it."""
    with store.connect() as conn:
        if conn.execute("SELECT 1 FROM desk_board WHERE mac = ?", (mac,)).fetchone() is None:
            return False
        if panel is not None:
            conn.execute("UPDATE desk_board SET panel = NULL WHERE panel = ?", (panel,))
        conn.execute("UPDATE desk_board SET panel = ? WHERE mac = ?", (panel, mac))
    return True


def forget(store: Store, mac: str) -> None:
    with store.connect() as conn:
        conn.execute("DELETE FROM desk_board WHERE mac = ?", (mac,))
