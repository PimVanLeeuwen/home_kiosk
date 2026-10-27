"""Recipes in SQLite (plan.md M30): one row per recipe, its canonical JSON as the body.

Replacing a recipe keeps the version before it once (`previous`), so one paste can be undone.
The nightly copy of the hub's database covers this table.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any, Literal

from ..store import Store
from . import photos
from .schema import Recipe

TABLES = """
CREATE TABLE IF NOT EXISTS recipe (
    id           TEXT PRIMARY KEY,   -- the recipe's slug, from its JSON
    title        TEXT NOT NULL,
    needs_review INTEGER NOT NULL DEFAULT 0,
    body         TEXT NOT NULL,      -- the canonical hub-recipe/1 JSON
    created_at   TEXT NOT NULL,
    updated_at   TEXT NOT NULL,
    previous     TEXT,               -- the body before the last replace, for one undo
    previous_at  TEXT
);
"""

Saved = Literal["added", "replaced", "unchanged"]


def ensure_tables(store: Store) -> None:
    with store.connect() as conn:
        conn.executescript(TABLES + photos.TABLES)


def _now(now: datetime | None) -> str:
    return (now or datetime.now(UTC)).isoformat(timespec="seconds")


def summaries(store: Store) -> list[dict[str, Any]]:
    """Every recipe for the list, by title: no phases, so the answer stays small."""
    with store.connect() as conn:
        rows = conn.execute(
            "SELECT id, title, needs_review, body, updated_at FROM recipe "
            "ORDER BY title COLLATE NOCASE"
        ).fetchall()
    pictures = photos.stamps(store)
    out = []
    for row in rows:
        body = json.loads(row["body"])
        out.append({"id": row["id"], "title": row["title"], "tags": body.get("tags", []),
                    "times": body.get("times", {}), "servings": body.get("servings"),
                    "needs_review": bool(row["needs_review"]), "updated_at": row["updated_at"],
                    "photo": pictures.get(row["id"])})
    return out


def get(store: Store, recipe_id: str) -> dict[str, Any] | None:
    with store.connect() as conn:
        row = conn.execute("SELECT * FROM recipe WHERE id = ?", (recipe_id,)).fetchone()
    if row is None:
        return None
    return {"recipe": json.loads(row["body"]), "needs_review": bool(row["needs_review"]),
            "created_at": row["created_at"], "updated_at": row["updated_at"],
            "previous_at": row["previous_at"], "photo": photos.stamps(store).get(recipe_id)}


def bodies(store: Store, ids: list[str] | None = None) -> dict[str, dict[str, Any]]:
    """The JSON of every recipe (or of these ids) by id, for Copy all and paste checks."""
    with store.connect() as conn:
        if ids is None:
            rows = conn.execute("SELECT id, body FROM recipe ORDER BY title COLLATE NOCASE")
        else:
            marks = ",".join("?" * len(ids))
            rows = conn.execute(f"SELECT id, body FROM recipe WHERE id IN ({marks})", ids)
        return {r["id"]: json.loads(r["body"]) for r in rows.fetchall()}


def save(store: Store, recipe: Recipe, now: datetime | None = None) -> Saved:
    """Adds the recipe, or replaces the one with its id (keeping that one for an undo)."""
    body = recipe.dump()
    text = json.dumps(body, ensure_ascii=False)
    stamp = _now(now)
    with store.connect() as conn:
        old = conn.execute("SELECT body FROM recipe WHERE id = ?", (recipe.id,)).fetchone()
        if old is None:
            conn.execute(
                "INSERT INTO recipe (id, title, needs_review, body, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (recipe.id, recipe.title, int(recipe.needs_review), text, stamp, stamp))
            return "added"
        if json.loads(old["body"]) == body:
            return "unchanged"
        conn.execute(
            "UPDATE recipe SET title = ?, needs_review = ?, body = ?, updated_at = ?, "
            "previous = ?, previous_at = ? WHERE id = ?",
            (recipe.title, int(recipe.needs_review), text, stamp, old["body"], stamp, recipe.id))
        return "replaced"


def undo(store: Store, recipe_id: str, now: datetime | None = None) -> bool:
    """Puts back the version before the last replace; there is only one undo."""
    with store.connect() as conn:
        row = conn.execute("SELECT previous FROM recipe WHERE id = ?", (recipe_id,)).fetchone()
        if row is None or row["previous"] is None:
            return False
        body = json.loads(row["previous"])
        conn.execute(
            "UPDATE recipe SET title = ?, needs_review = ?, body = ?, updated_at = ?, "
            "previous = NULL, previous_at = NULL WHERE id = ?",
            (body["title"], int(body.get("needs_review", False)), row["previous"], _now(now),
             recipe_id))
        return True


def delete(store: Store, recipe_id: str) -> bool:
    photos.delete(store, recipe_id)  # SQLite only cascades with foreign keys switched on
    with store.connect() as conn:
        return conn.execute("DELETE FROM recipe WHERE id = ?", (recipe_id,)).rowcount > 0
