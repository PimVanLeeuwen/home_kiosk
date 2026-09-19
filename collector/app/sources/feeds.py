"""Feed selection for /api/news.

The fetching itself lands in M4; what lives here now is the part that needed
deciding rather than discovering — how a group picks which headlines to show.

A group has more feeds than slots (the "Self-hosted, Apple & Linux" group has
five feeds and three slots). Sorting the union by recency would let one prolific
feed take every slot: 9to5Mac publishes on the order of a hundred items a day,
against a handful from It's FOSS. So selection is round-robin across feeds, and
the starting feed advances each fetch so the ones that missed out get a turn.
"""

from __future__ import annotations

import asyncio
import logging
import re
from datetime import UTC, datetime
from typing import Any
from zoneinfo import ZoneInfo

import feedparser
import httpx

from ..models import News, NewsGroup, NewsItem
from ..store import Store

log = logging.getLogger(__name__)

OFFSET_KEY = "news_offsets"
SEEN_KEY = "news_seen"

FETCH_TIMEOUT_SECONDS = 20
# Feeds are read, never rendered; a plain identifying agent is enough. Some
# sites 429 an empty or default agent.
USER_AGENT = "Mozilla/5.0 (compatible; desk-dashboard/1.0)"
# Enough to notice a repeat, small enough to keep the cache row light.
SEEN_PER_GROUP = 200

_HN_POINTS = re.compile(r"Points:\s*(\d+)")


def interleave(
    items_by_feed: list[list[Any]],
    limit: int,
    offset: int = 0,
    *,
    key: Any = None,
) -> list[Any]:
    """Pick up to `limit` items, round-robin across feeds.

    Every feed contributes its newest unused item before any feed contributes a
    second, so with at least `limit` non-empty feeds no feed appears twice.
    `offset` rotates which feed goes first, so a feed starved on one fetch leads
    the next. The result is re-sorted newest-first for display.
    """
    feeds = [list(f) for f in items_by_feed if f]
    if not feeds or limit <= 0:
        return []

    offset %= len(feeds)
    ordered = feeds[offset:] + feeds[:offset]

    picked: list[Any] = []
    depth = 0
    deepest = max(len(f) for f in ordered)
    while len(picked) < limit and depth < deepest:
        for feed in ordered:
            if depth < len(feed):
                picked.append(feed[depth])
                if len(picked) == limit:
                    break
        depth += 1

    if key is not None:
        picked.sort(key=key, reverse=True)
    return picked


def next_offset(store: Any, group_id: str, feed_count: int) -> int:
    """Read the group's rotation offset and advance it for the next fetch."""
    offsets = store.get_cache(OFFSET_KEY) or {}
    current = int(offsets.get(group_id, 0))
    offsets[group_id] = (current + 1) % max(feed_count, 1)
    store.put_cache(OFFSET_KEY, offsets)
    return current


# --- normalising ------------------------------------------------------------


def truncate(title: str, limit: int) -> str:
    """Trim to `limit` characters at a word boundary, per §5.

    Done server-side because two lines at 23px is roughly 70 characters and
    Dutch outlet headlines routinely exceed it — CSS clipping breaks mid-word.
    """
    text = " ".join(title.split())
    if len(text) <= limit:
        return text
    cut = text[:limit]
    space = cut.rfind(" ")
    if space > limit * 0.6:      # only honour a boundary that is not far back
        cut = cut[:space]
    return cut.rstrip(" ,.;:–—-") + "…"


def age_label(published: datetime, now: datetime) -> str:
    """Precomputed server-side so the frontend does no date maths, per §5."""
    seconds = max(0, (now - published).total_seconds())
    minutes = int(seconds // 60)
    if minutes < 1:
        return "just now"
    if minutes < 60:
        return f"{minutes} min ago"
    hours = int(seconds // 3600)
    if hours < 24:
        return f"{hours} hr ago"
    days = int(seconds // 86400)
    return f"{days} day{'s' if days > 1 else ''} ago"


def _published(entry: Any, now: datetime) -> datetime:
    parsed = entry.get("published_parsed") or entry.get("updated_parsed")
    if not parsed:
        return now
    return datetime(*parsed[:6], tzinfo=UTC)


def _meta(entry: Any) -> str | None:
    """Source-specific detail where one exists, else None and the view falls
    back to the age label. Hacker News carries its score in the summary body."""
    match = _HN_POINTS.search(entry.get("summary", "") or "")
    return f"{match.group(1)} points" if match else None


def _normalise(entry: Any, source: str, cfg: dict[str, Any], now: datetime) -> NewsItem | None:
    title = (entry.get("title") or "").strip()
    link = (entry.get("link") or "").strip()
    if not title or not link:
        return None
    published = _published(entry, now)
    return NewsItem(
        title=truncate(title, cfg["news"].get("title_max_chars", 70)),
        source=source,
        published=published,
        age_label=age_label(published, now),
        url=link,
        meta=_meta(entry),
    )


# --- fetching ---------------------------------------------------------------


def _feed_url(feed: Any) -> str:
    return feed["url"] if isinstance(feed, dict) else str(feed)


async def _fetch_feed(
    client: httpx.AsyncClient, feed: Any, cfg: dict[str, Any], now: datetime
) -> list[NewsItem]:
    """One feed's items, newest first. A failing feed yields nothing rather
    than failing the whole refresh — one dead source must not blank the view."""
    url = _feed_url(feed)
    try:
        resp = await client.get(url, timeout=FETCH_TIMEOUT_SECONDS)
        resp.raise_for_status()
    except Exception as exc:
        log.warning("feed %s failed: %s", url, exc)
        return []

    # feedparser is synchronous and does real parsing work; keep it off the loop.
    parsed = await asyncio.to_thread(feedparser.parse, resp.text)
    if not parsed.entries:
        log.warning("feed %s returned no entries", url)
        return []

    name = feed.get("name") if isinstance(feed, dict) else None
    source = name or (parsed.feed.get("title") or url)

    items = [_normalise(e, source, cfg, now) for e in parsed.entries]
    items = [i for i in items if i is not None]
    items.sort(key=lambda i: i.published, reverse=True)
    return items


async def collect(cfg: dict[str, Any], store: Store) -> News:
    news_cfg = cfg["news"]
    tz = ZoneInfo(cfg.get("timezone", "UTC"))
    now = datetime.now(tz)
    limit = news_cfg.get("max_per_group", 3)

    seen_all: dict[str, list[str]] = store.get_cache(SEEN_KEY) or {}
    groups: list[NewsGroup] = []
    feed_count = 0

    async with httpx.AsyncClient(
        follow_redirects=True, headers={"User-Agent": USER_AGENT}
    ) as client:
        for group in news_cfg.get("groups", []):
            feeds = group.get("feeds") or []
            feed_count += len(feeds)
            if not feeds:
                continue

            per_feed = await asyncio.gather(
                *(_fetch_feed(client, f, cfg, now) for f in feeds)
            )

            offset = next_offset(store, group["id"], len(feeds))
            chosen = interleave(
                list(per_feed), limit, offset, key=lambda i: i.published
            )

            # new_count = items first seen since the previous fetch.
            previously = set(seen_all.get(group["id"], []))
            new_count = sum(1 for i in chosen if i.url not in previously)

            everything = [i.url for feed in per_feed for i in feed]
            seen_all[group["id"]] = (everything + list(previously))[:SEEN_PER_GROUP]

            groups.append(
                NewsGroup(
                    id=group["id"],
                    title=group["title"],
                    new_count=new_count,
                    items=chosen,
                )
            )

    store.put_cache(SEEN_KEY, seen_all)
    return News(as_of=now, stale=False, groups=groups, feed_count=feed_count)
