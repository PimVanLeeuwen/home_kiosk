"""Device keys for the desk panels (plan.md M16): what lets a board change
something (save a story; later lights and music), as `same_origin_json` only
keeps other websites out of the owner's browser.

A board gets a key when it is given a panel in Settings, Desk panels. The hub
hands the key over once, in the board's next answer, and then keeps only its
SHA-256: the board stores it and sends it as `Authorization: Bearer <key>`.
Taking the panel away (or forgetting the board) revokes the key; Settings can
also revoke it or issue a new one.
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime
from typing import Literal

from fastapi import HTTPException, Request

from .store import Store

KeyState = Literal["none", "pending", "active"]

TABLES = """
CREATE TABLE IF NOT EXISTS desk_key (
    mac        TEXT PRIMARY KEY,
    key_hash   TEXT NOT NULL,
    pending    TEXT,          -- the key itself until the board has picked it up
    issued_at  TEXT NOT NULL
);
"""


def _hash(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


def ensure_tables(store: Store) -> None:
    with store.connect() as conn:
        conn.executescript(TABLES)


def issue(store: Store, mac: str, now: datetime | None = None) -> None:
    """A fresh key for the board, replacing any earlier one; handed over once."""
    key = secrets.token_urlsafe(32)
    with store.connect() as conn:
        conn.execute("INSERT OR REPLACE INTO desk_key (mac, key_hash, pending, issued_at)"
                     " VALUES (?, ?, ?, ?)",
                     (mac, _hash(key), key, (now or datetime.now(UTC)).isoformat()))


def revoke(store: Store, mac: str) -> None:
    with store.connect() as conn:
        conn.execute("DELETE FROM desk_key WHERE mac = ?", (mac,))


def has_key(store: Store, mac: str) -> bool:
    with store.connect() as conn:
        return conn.execute("SELECT 1 FROM desk_key WHERE mac = ?", (mac,)).fetchone() is not None


def hand_over(store: Store, mac: str) -> str | None:
    """The board's new key, once: afterwards the hub keeps only its hash."""
    with store.connect() as conn:
        row = conn.execute("SELECT pending FROM desk_key WHERE mac = ?", (mac,)).fetchone()
        if row is None or row["pending"] is None:
            return None
        conn.execute("UPDATE desk_key SET pending = NULL WHERE mac = ?", (mac,))
    return row["pending"]


def states(store: Store) -> dict[str, KeyState]:
    with store.connect() as conn:
        rows = conn.execute("SELECT mac, pending FROM desk_key").fetchall()
    return {r["mac"]: "pending" if r["pending"] else "active" for r in rows}


def board_for(store: Store, key: str) -> str | None:
    """The MAC of the board with this key, if it has picked it up."""
    with store.connect() as conn:
        row = conn.execute("SELECT mac FROM desk_key WHERE key_hash = ? AND pending IS NULL",
                           (_hash(key),)).fetchone()
    return row["mac"] if row else None


def board_key(request: Request) -> str:
    """FastAPI dependency for the panels' own writes: the board's MAC, or 401."""
    scheme, _, key = request.headers.get("authorization", "").partition(" ")
    mac = board_for(request.app.state.store, key.strip()) if scheme.lower() == "bearer" else None
    if mac is None:
        raise HTTPException(401, "This board has no valid key: give it a panel in Settings.")
    return mac
