"""Which board is which desk panel (plan.md M16).

Every board runs the same firmware and only knows its own MAC address (the one
written on its back). It asks `/api/desk/board/<mac>`; the hub notes when it
was last seen and with which firmware, and answers with the screens of the
panel it is assigned to in Settings → Desk panels. Each panel has at most one
board: assigning a panel takes it from the board that had it. "Update now" in
Settings asks a board to install the hub's firmware at once: the flag goes out
with its next answer, once.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel

from . import desk_keys
from .store import Store

Panel = Literal["now", "home", "house", "test"]
MAC = re.compile(r"^[0-9a-f]{2}(:[0-9a-f]{2}){5}$")

TABLES = """
CREATE TABLE IF NOT EXISTS desk_board (
    mac        TEXT PRIMARY KEY,  -- e8:f6:0a:e4:42:b0
    panel      TEXT,              -- now, home, house, test; NULL until assigned
    first_seen TEXT NOT NULL,
    last_seen  TEXT NOT NULL,
    firmware   TEXT NOT NULL DEFAULT '',
    update_requested INTEGER NOT NULL DEFAULT 0
);
"""


class Board(BaseModel):
    mac: str
    panel: Panel | None
    first_seen: datetime
    last_seen: datetime
    firmware: str
    update_requested: bool = False
    key: desk_keys.KeyState = "none"  # its device key (app/desk_keys.py)


def ensure_tables(store: Store) -> None:
    desk_keys.ensure_tables(store)
    with store.connect() as conn:
        conn.executescript(TABLES)
        columns = {r["name"] for r in conn.execute("PRAGMA table_info(desk_board)")}
        if "update_requested" not in columns:  # added after the table shipped
            conn.execute("ALTER TABLE desk_board"
                         " ADD COLUMN update_requested INTEGER NOT NULL DEFAULT 0")
        assigned = [r["mac"] for r in conn.execute(
            "SELECT mac FROM desk_board WHERE panel IS NOT NULL")]
    # Boards given a panel before there were keys get one now.
    for mac in assigned:
        if not desk_keys.has_key(store, mac):
            desk_keys.issue(store, mac)


class Visit(BaseModel):
    panel: Panel | None
    update: bool  # install the hub's firmware now
    key: str | None = None  # its new device key, handed over once


def check_in(store: Store, mac: str, firmware: str, now: datetime | None = None) -> Visit:
    """Notes the board's visit: its panel, and whether to update now (asked once)."""
    at = (now or datetime.now(UTC)).isoformat()
    with store.connect() as conn:
        conn.execute(
            "INSERT INTO desk_board (mac, first_seen, last_seen, firmware) VALUES (?, ?, ?, ?)"
            " ON CONFLICT (mac) DO UPDATE SET last_seen = excluded.last_seen,"
            " firmware = excluded.firmware",
            (mac, at, at, firmware[:40]))
        row = conn.execute("SELECT panel, update_requested FROM desk_board WHERE mac = ?",
                           (mac,)).fetchone()
        if row["update_requested"]:
            conn.execute("UPDATE desk_board SET update_requested = 0 WHERE mac = ?", (mac,))
    return Visit(panel=row["panel"], update=bool(row["update_requested"]),
                 key=desk_keys.hand_over(store, mac) if row["panel"] else None)


def boards(store: Store) -> list[Board]:
    with store.connect() as conn:
        rows = conn.execute("SELECT * FROM desk_board ORDER BY first_seen, mac").fetchall()
    keys = desk_keys.states(store)
    return [Board(**dict(r), key=keys.get(r["mac"], "none")) for r in rows]


def assign(store: Store, mac: str, panel: Panel | None) -> bool:
    """Gives the board a panel (or none); False when the hub has never seen it.
    A board with a panel has a device key; one without has none."""
    with store.connect() as conn:
        if conn.execute("SELECT 1 FROM desk_board WHERE mac = ?", (mac,)).fetchone() is None:
            return False
        losing = []
        if panel is not None:
            losing = [r["mac"] for r in conn.execute(
                "SELECT mac FROM desk_board WHERE panel = ? AND mac != ?", (panel, mac))]
            conn.execute("UPDATE desk_board SET panel = NULL WHERE panel = ?", (panel,))
        conn.execute("UPDATE desk_board SET panel = ? WHERE mac = ?", (panel, mac))
    for other in losing:
        desk_keys.revoke(store, other)
    if panel is None:
        desk_keys.revoke(store, mac)
    elif not desk_keys.has_key(store, mac):
        desk_keys.issue(store, mac)
    return True


def forget(store: Store, mac: str) -> None:
    with store.connect() as conn:
        conn.execute("DELETE FROM desk_board WHERE mac = ?", (mac,))
    desk_keys.revoke(store, mac)


def request_update(store: Store, mac: str) -> None:
    with store.connect() as conn:
        conn.execute("UPDATE desk_board SET update_requested = 1 WHERE mac = ?", (mac,))
