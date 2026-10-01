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
import html
import logging
import re
from datetime import UTC, datetime
from typing import Any
from zoneinfo import ZoneInfo

import feedparser
import httpx

from ..models import News, NewsGroup, NewsItem
from ..news import store as news_store
from ..store import Store

log = logging.getLogger(__name__)

OFFSET_KEY = "news_offsets"
SEEN_KEY = "news_seen"

# Reading view, served at /api/news/full. Cached alongside the kiosk payload
# from the same fetch.
FULL_CACHE_KEY = "news_full"
FULL_MAX_PER_GROUP = 40
# Per-feed ceiling inside the reading view. Without it, pure recency lets the
# loudest feed bury the rest: measured on real data, Bloomberg took 20 of 40
# Tech slots, and Hacker News, OMG Ubuntu and It's FOSS vanished from the
# five-feed group entirely.
FULL_MAX_PER_FEED = 10

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
    # Feeds escape their titles ("Apple&#8217;s"); decode before truncating so
    # the entity is not counted toward the character limit or split in half.
    title = html.unescape(entry.get("title") or "").strip()
    link = (entry.get("link") or "").strip()
    if not title or not link:
        return None
    published = _published(entry, now)
    item = NewsItem(
        title=truncate(title, cfg["news"].get("title_max_chars", 70)),
        source=source,
        published=published,
        age_label=age_label(published, now),
        url=link,
        meta=_meta(entry),
    )
    item._full_title = " ".join(title.split())
    return item


# --- fetching ---------------------------------------------------------------


def _feed_url(feed: Any) -> str:
    return feed["url"] if isinstance(feed, dict) else str(feed)


def _reason(exc: Exception) -> str:
    """A short reason for the Settings feed list."""
    if isinstance(exc, httpx.HTTPStatusError):
        return f"HTTP {exc.response.status_code}"
    if isinstance(exc, httpx.TimeoutException):
        return "Timed out"
    if isinstance(exc, httpx.TransportError):
        return "Not reachable"
    return type(exc).__name__


async def _fetch_feed(
    client: httpx.AsyncClient, feed: Any, cfg: dict[str, Any], now: datetime,
    errors: dict[int, str] | None = None,
) -> list[NewsItem]:
    """One feed's items, newest first. A failing feed yields nothing rather
    than failing the whole refresh — one dead source must not blank the view.
    Failures are noted in `errors` by feed id, for the Settings page."""
    url = _feed_url(feed)
    feed_id = feed.get("feed_id") if isinstance(feed, dict) else None
    try:
        resp = await client.get(url, timeout=FETCH_TIMEOUT_SECONDS)
        resp.raise_for_status()
    except Exception as exc:
        # Include the exception class: timeouts stringify to an empty message,
        # so "feed X failed: " on its own says nothing about why.
        log.warning("feed %s failed: %s: %s", url, type(exc).__name__, exc or "(no detail)")
        if errors is not None and feed_id is not None:
            errors[feed_id] = _reason(exc)
        return []

    # feedparser is synchronous and does real parsing work; keep it off the loop.
    parsed = await asyncio.to_thread(feedparser.parse, resp.text)
    if not parsed.entries:
        log.warning("feed %s returned no entries", url)
        if errors is not None and feed_id is not None:
            errors[feed_id] = "No items: not a feed?"
        return []

    name = feed.get("name") if isinstance(feed, dict) else None
    source = name or (parsed.feed.get("title") or url)

    items = [_normalise(e, source, cfg, now) for e in parsed.entries]
    items = [i for i in items if i is not None]
    items.sort(key=lambda i: i.published, reverse=True)
    return items


async def collect(
    cfg: dict[str, Any], store: Store, transport: httpx.AsyncBaseTransport | None = None
) -> News:
    """Fetch every feed once and cache two views of the same data.

    Returns the kiosk payload — a few interleaved headlines per group — and
    additionally writes a `news_full` payload holding everything, newest first,
    for reading on a phone. Both come from one set of requests: the full lists
    are already in memory and were previously thrown away.
    """
    news_cfg = cfg["news"]
    # The feed list as edited in Settings; config.yaml until it is seeded.
    feed_groups = news_store.as_config(store) or news_cfg.get("groups", [])
    errors: dict[int, str] = {}
    tz = ZoneInfo(cfg.get("timezone", "UTC"))
    now = datetime.now(tz)
    limit = news_cfg.get("max_per_group", 3)

    seen_all: dict[str, list[str]] = store.get_cache(SEEN_KEY) or {}
    groups: list[NewsGroup] = []
    full_groups: list[NewsGroup] = []
    feed_count = 0

    async with httpx.AsyncClient(
        follow_redirects=True, headers={"User-Agent": USER_AGENT}, transport=transport
    ) as client:
        for group in feed_groups:
            feeds = group.get("feeds") or []
            feed_count += len(feeds)
            if not feeds:
                continue

            per_feed = await asyncio.gather(
                *(_fetch_feed(client, f, cfg, now, errors) for f in feeds)
            )
            for feed, items in zip(feeds, per_feed, strict=True):
                if isinstance(feed, dict) and feed.get("feed_id") is not None:
                    news_store.record_fetch(
                        store, feed["feed_id"], now, len(items), errors.get(feed["feed_id"]))
            # Every item, untruncated, into the Home hub's article store.
            news_store.save_articles(store, group["id"], [
                {"url": i.url, "title": i._full_title or i.title, "source": i.source,
                 "published": i.published}
                for feed_items in per_feed for i in feed_items
            ], now)

            offset = next_offset(store, group["id"], len(feeds))
            chosen = interleave(
                list(per_feed), limit, offset, key=lambda i: i.published
            )

            # new_count = items first seen since the previous fetch.
            previously = set(seen_all.get(group["id"], []))
            new_count = sum(1 for i in chosen if i.url not in previously)

            # Reading view: everything this group returned, newest first. No
            # interleaving — with the whole list on screen there is nothing for
            # fair rotation to protect against.
            merged: dict[str, NewsItem] = {}
            for feed in per_feed:
                for item in feed[:FULL_MAX_PER_FEED]:
                    merged.setdefault(item.url, item)   # same story via two feeds
            ordered = sorted(merged.values(), key=lambda i: i.published, reverse=True)
            full_items = ordered[:FULL_MAX_PER_GROUP]

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
            full_groups.append(
                NewsGroup(
                    id=group["id"],
                    title=group["title"],
                    new_count=sum(1 for i in full_items if i.url not in previously),
                    items=full_items,
                )
            )

    store.put_cache(SEEN_KEY, seen_all)
    news_store.prune(store, now)
    store.put_cache(
        FULL_CACHE_KEY,
        News(as_of=now, stale=False, groups=full_groups, feed_count=feed_count).model_dump(
            mode="json"
        ),
    )
    return News(as_of=now, stale=False, groups=groups, feed_count=feed_count)
