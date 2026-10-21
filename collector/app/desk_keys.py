"""Device keys for the desk panels (plan.md M16): what lets a board change
something (save a story; later lights and music), as `same_origin_json` only
keeps other websites out of the owner's browser.

A board gets a key when it is given a panel in Settings, Desk panels. The hub
hands the key over in the board's answers until the board shows it has it (it
sends the key with its polls and writes as `Authorization: Bearer <key>`); from
then on the hub keeps only its SHA-256. A handover the board missed so is simply
repeated. Taking the panel away (or forgetting the board) revokes the key;
Settings can also revoke it or issue a new one.
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
    pending    TEXT,          -- the key itself until the board has shown it has it
    issued_at  TEXT NOT NULL,
    used_at    TEXT           -- when the board first sent it
);
"""


def _hash(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


def ensure_tables(store: Store) -> None:
    with store.connect() as conn:
        conn.executescript(TABLES)
        if "used_at" not in {r["name"] for r in conn.execute("PRAGMA table_info(desk_key)")}:
            conn.execute("ALTER TABLE desk_key ADD COLUMN used_at TEXT")  # added after it shipped
        # Handed over once, never confirmed (before keys waited for the board):
        # the board may never have stored it, so it gets a new one.
        unconfirmed = [r["mac"] for r in conn.execute(
            "SELECT mac FROM desk_key WHERE pending IS NULL AND used_at IS NULL")]
    for mac in unconfirmed:
        issue(store, mac)


def issue(store: Store, mac: str, now: datetime | None = None) -> None:
    """A fresh key for the board, replacing any earlier one; handed over until confirmed."""
    key = secrets.token_urlsafe(32)
    with store.connect() as conn:
        conn.execute("INSERT OR REPLACE INTO desk_key (mac, key_hash, pending, issued_at, used_at)"
                     " VALUES (?, ?, ?, ?, NULL)",
                     (mac, _hash(key), key, (now or datetime.now(UTC)).isoformat()))


def revoke(store: Store, mac: str) -> None:
    with store.connect() as conn:
        conn.execute("DELETE FROM desk_key WHERE mac = ?", (mac,))


def has_key(store: Store, mac: str) -> bool:
    with store.connect() as conn:
        return conn.execute("SELECT 1 FROM desk_key WHERE mac = ?", (mac,)).fetchone() is not None


def _confirm(conn, mac: str, now: datetime | None = None) -> None:
    """The board has its key: forget the key itself, keep only its hash."""
    conn.execute("UPDATE desk_key SET pending = NULL, used_at = COALESCE(used_at, ?)"
                 " WHERE mac = ?", ((now or datetime.now(UTC)).isoformat(), mac))


def hand_over(store: Store, mac: str, presented: str = "") -> str | None:
    """The board's new key, in every answer until the board presents it (`presented`,
    from its Authorization header); None once it has it, or when it has no key."""
    with store.connect() as conn:
        row = conn.execute("SELECT key_hash, pending FROM desk_key WHERE mac = ?",
                           (mac,)).fetchone()
        if row is None or row["pending"] is None:
            return None
        if presented and secrets.compare_digest(_hash(presented), row["key_hash"]):
            _confirm(conn, mac)
            return None
    return row["pending"]


def states(store: Store) -> dict[str, KeyState]:
    with store.connect() as conn:
        rows = conn.execute("SELECT mac, pending FROM desk_key").fetchall()
    return {r["mac"]: "pending" if r["pending"] else "active" for r in rows}


def board_for(store: Store, key: str) -> str | None:
    """The MAC of the board with this key; its first use confirms the handover."""
    if not key:
        return None
    with store.connect() as conn:
        row = conn.execute("SELECT mac, pending FROM desk_key WHERE key_hash = ?",
                           (_hash(key),)).fetchone()
        if row is not None and row["pending"] is not None:
            _confirm(conn, row["mac"])
    return row["mac"] if row else None


def presented(request: Request) -> str:
    """The key in the request's `Authorization: Bearer <key>`, or ""."""
    scheme, _, key = request.headers.get("authorization", "").partition(" ")
    return key.strip() if scheme.lower() == "bearer" else ""


def board_key(request: Request) -> str:
    """FastAPI dependency for the panels' own writes: the board's MAC, or 401."""
    key = presented(request)
    mac = board_for(request.app.state.store, key) if key else None
    if mac is None:
        raise HTTPException(401, "This board has no valid key: give it a panel in Settings.")
    return mac
