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

from typing import Any

OFFSET_KEY = "news_offsets"


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
