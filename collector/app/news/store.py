"""News storage: the feed list (editable in Settings) and every article seen.

Feeds and groups are seeded from config.yaml once, like the service catalog.
Articles are written by the feed job; their read state is shared by the
household (there are no accounts) and they are kept for RETENTION.
"""

from __future__ import annotations

import hashlib
import re
from datetime import UTC, datetime, timedelta
from typing import Any

from pydantic import BaseModel

from ..store import Store

RETENTION = timedelta(days=7)

TABLES = """
CREATE TABLE IF NOT EXISTS feed_group (
    id    TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    sort  INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS feed (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    group_id    TEXT NOT NULL REFERENCES feed_group(id) ON DELETE CASCADE,
    url         TEXT NOT NULL,
    name        TEXT,
    sort        INTEGER NOT NULL,
    -- The last fetch: when, how many items, and why it failed if it did.
    checked_at  TEXT,
    item_count  INTEGER,
    error       TEXT
);

CREATE TABLE IF NOT EXISTS article (
    id         TEXT PRIMARY KEY,   -- from the URL, stable across fetches
    url        TEXT NOT NULL,
    title      TEXT NOT NULL,
    source     TEXT NOT NULL,
    group_id   TEXT NOT NULL,
    published  TEXT NOT NULL,
    first_seen TEXT NOT NULL,
    read_at    TEXT
);
CREATE INDEX IF NOT EXISTS article_published ON article (published);
"""


class Feed(BaseModel):
    id: int
    group_id: str
    url: str
    name: str | None
    checked_at: datetime | None = None
    item_count: int | None = None
    error: str | None = None


class FeedGroup(BaseModel):
    id: str
    title: str
    feeds: list[Feed]


class Article(BaseModel):
    id: str
    url: str
    title: str
    source: str
    group_id: str
    published: datetime
    read: bool


def article_id(url: str) -> str:
    return hashlib.sha256(url.encode()).hexdigest()[:16]


def ensure_tables(store: Store) -> None:
    with store.connect() as conn:
        conn.executescript(TABLES)


# --- feeds -------------------------------------------------------------------------


def seed(store: Store, cfg: dict[str, Any]) -> bool:
    """Copy the config.yaml groups into an empty feed list. Returns whether it did."""
    with store.connect() as conn:
        if conn.execute("SELECT 1 FROM feed_group LIMIT 1").fetchone():
            return False
        for g_sort, group in enumerate((cfg.get("news") or {}).get("groups", [])):
            conn.execute("INSERT INTO feed_group (id, title, sort) VALUES (?, ?, ?)",
                         (group["id"], group["title"], g_sort))
            for f_sort, feed in enumerate(group.get("feeds") or []):
                url = feed["url"] if isinstance(feed, dict) else str(feed)
                name = feed.get("name") if isinstance(feed, dict) else None
                conn.execute(
                    "INSERT INTO feed (group_id, url, name, sort) VALUES (?, ?, ?, ?)",
                    (group["id"], url, name, f_sort))
    return True


def groups(store: Store) -> list[FeedGroup]:
    with store.connect() as conn:
        group_rows = conn.execute("SELECT * FROM feed_group ORDER BY sort, title").fetchall()
        feed_rows = conn.execute("SELECT * FROM feed ORDER BY sort, id").fetchall()
    feeds: dict[str, list[Feed]] = {}
    for r in feed_rows:
        feeds.setdefault(r["group_id"], []).append(Feed.model_validate(dict(r)))
    return [FeedGroup(id=g["id"], title=g["title"], feeds=feeds.get(g["id"], []))
            for g in group_rows]


def as_config(store: Store) -> list[dict[str, Any]]:
    """The feed list in config.yaml's shape, for the feed job."""
    return [
        {"id": g.id, "title": g.title,
         "feeds": [{"url": f.url, "name": f.name, "feed_id": f.id} for f in g.feeds]}
        for g in groups(store)
    ]


def slug(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:30] or "group"


def add_group(store: Store, title: str) -> str:
    taken = {g.id for g in groups(store)}
    base = slug(title)
    group_id, n = base, 2
    while group_id in taken:
        group_id, n = f"{base}-{n}", n + 1
    with store.connect() as conn:
        sort = conn.execute("SELECT COALESCE(MAX(sort) + 1, 0) FROM feed_group").fetchone()[0]
        conn.execute("INSERT INTO feed_group (id, title, sort) VALUES (?, ?, ?)",
                     (group_id, title, sort))
    return group_id


def rename_group(store: Store, group_id: str, title: str) -> bool:
    with store.connect() as conn:
        return conn.execute("UPDATE feed_group SET title = ? WHERE id = ?",
                            (title, group_id)).rowcount > 0


def delete_group(store: Store, group_id: str) -> bool:
    with store.connect() as conn:
        conn.execute("DELETE FROM feed WHERE group_id = ?", (group_id,))
        return conn.execute("DELETE FROM feed_group WHERE id = ?", (group_id,)).rowcount > 0


def add_feed(store: Store, group_id: str, url: str, name: str | None) -> int | None:
    with store.connect() as conn:
        if not conn.execute("SELECT 1 FROM feed_group WHERE id = ?", (group_id,)).fetchone():
            return None
        sort = conn.execute("SELECT COALESCE(MAX(sort) + 1, 0) FROM feed WHERE group_id = ?",
                            (group_id,)).fetchone()[0]
        return conn.execute(
            "INSERT INTO feed (group_id, url, name, sort) VALUES (?, ?, ?, ?)",
            (group_id, url, name, sort)).lastrowid


def update_feed(store: Store, feed_id: int, group_id: str, url: str, name: str | None) -> bool:
    with store.connect() as conn:
        if not conn.execute("SELECT 1 FROM feed_group WHERE id = ?", (group_id,)).fetchone():
            return False
        return conn.execute(
            "UPDATE feed SET group_id = ?, url = ?, name = ?, error = NULL WHERE id = ?",
            (group_id, url, name, feed_id)).rowcount > 0


def delete_feed(store: Store, feed_id: int) -> bool:
    with store.connect() as conn:
        return conn.execute("DELETE FROM feed WHERE id = ?", (feed_id,)).rowcount > 0


def record_fetch(store: Store, feed_id: int, now: datetime, count: int,
                 error: str | None) -> None:
    with store.connect() as conn:
        conn.execute(
            "UPDATE feed SET checked_at = ?, item_count = ?, error = ? WHERE id = ?",
            (now.isoformat(), count, error, feed_id))


# --- articles -------------------------------------------------------------------------


def save_articles(store: Store, group_id: str, items: list[dict[str, Any]],
                  now: datetime) -> int:
    """Insert new articles; known ones keep their read state. Returns how many were new."""
    with store.connect() as conn:
        before = conn.total_changes
        conn.executemany(
            "INSERT INTO article (id, url, title, source, group_id, published, first_seen) "
            "VALUES (?, ?, ?, ?, ?, ?, ?) ON CONFLICT(id) DO NOTHING",
            [(article_id(i["url"]), i["url"], i["title"], i["source"], group_id,
              i["published"].isoformat(), now.isoformat()) for i in items])
        return conn.total_changes - before


def prune(store: Store, now: datetime | None = None) -> int:
    cutoff = ((now or datetime.now(UTC)) - RETENTION).isoformat()
    with store.connect() as conn:
        return conn.execute("DELETE FROM article WHERE published < ?", (cutoff,)).rowcount


def _row(r: Any) -> Article:
    return Article(id=r["id"], url=r["url"], title=r["title"], source=r["source"],
                   group_id=r["group_id"], published=r["published"],
                   read=r["read_at"] is not None)


def articles(store: Store, *, group: str | None = None, unread: bool = False,
             q: str | None = None, limit: int = 50, offset: int = 0
             ) -> tuple[list[Article], int]:
    """Newest first, filtered; also returns the total for paging."""
    where, args = [], []
    if group:
        where.append("group_id = ?")
        args.append(group)
    if unread:
        where.append("read_at IS NULL")
    if q and q.strip():
        for word in q.split():
            # Every word must appear in the title or the source.
            where.append("(title LIKE ? ESCAPE '\\' OR source LIKE ? ESCAPE '\\')")
            pattern = "%" + re.sub(r"([%_\\])", r"\\\1", word) + "%"
            args += [pattern, pattern]
    clause = f" WHERE {' AND '.join(where)}" if where else ""
    with store.connect() as conn:
        total = conn.execute(f"SELECT COUNT(*) FROM article{clause}", args).fetchone()[0]
        rows = conn.execute(
            f"SELECT * FROM article{clause} ORDER BY published DESC, id LIMIT ? OFFSET ?",
            (*args, limit, offset)).fetchall()
    return [_row(r) for r in rows], total


def article(store: Store, aid: str) -> Article | None:
    with store.connect() as conn:
        r = conn.execute("SELECT * FROM article WHERE id = ?", (aid,)).fetchone()
    return _row(r) if r else None


def unread_counts(store: Store) -> dict[str, int]:
    with store.connect() as conn:
        rows = conn.execute(
            "SELECT group_id, COUNT(*) AS n FROM article WHERE read_at IS NULL GROUP BY group_id")
        return {r["group_id"]: r["n"] for r in rows}


def mark_read(store: Store, aid: str, read: bool, now: datetime | None = None) -> bool:
    stamp = (now or datetime.now(UTC)).isoformat() if read else None
    with store.connect() as conn:
        return conn.execute("UPDATE article SET read_at = ? WHERE id = ?",
                            (stamp, aid)).rowcount > 0


def mark_all_read(store: Store, group: str | None = None, now: datetime | None = None) -> int:
    stamp = (now or datetime.now(UTC)).isoformat()
    query, args = "UPDATE article SET read_at = ? WHERE read_at IS NULL", [stamp]
    if group:
        query, args = query + " AND group_id = ?", [stamp, group]
    with store.connect() as conn:
        return conn.execute(query, args).rowcount
