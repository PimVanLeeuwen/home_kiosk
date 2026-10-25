"""Headlines, one story per event (plan.md M26, step 4).

Hourly from 06:00 to 23:00 the hub gives Haiku the last WINDOW of articles from
every feed (numbered, with source, title and the feed's first line) and asks
which report the same event, with one sentence for each story that more than one
feed covers, written only from those lines. The grouping is kept in the cache
(`stories`); headlines.collect builds the top stories from it, ranked by how
many feeds carry an event and then by the newest, so the ranking is counted,
not chosen. Without a fresh grouping (AI off, the cap, no answer) the headlines
are the newest of each group, as before.

Only public text goes to Claude: titles and first lines from the feeds.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from .. import ai
from ..store import Store

log = logging.getLogger(__name__)

FEATURE = "headlines"
CACHE_KEY = "stories"
WINDOW = timedelta(hours=12)
MAX_ARTICLES = 80
LINE_CHARS = 160
SUMMARY_MAX = 220
FRESH = timedelta(hours=8)  # the night's last grouping still holds at 06:00
HOURS = "6-23"  # local hours it runs, at a few minutes past

SYSTEM = (
    "You group news articles from several feeds into stories, one story per real-world event. "
    "Put articles in the same story only when they report the same event, not merely the same "
    "topic. Use every article number exactly once; an article about something no other "
    "article covers is a story of its own. For a story of two or more articles, write "
    "`summary`: one plain sentence of at most 30 words on what happened, using only the "
    "titles and first lines given, in the language most of its articles use (English or "
    "Dutch). For a single article, leave `summary` empty. No markdown, no emoji."
)

SCHEMA = {
    "type": "object",
    "properties": {
        "stories": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "articles": {"type": "array", "items": {"type": "integer"}},
                    "summary": {"type": "string"},
                },
                "required": ["articles", "summary"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["stories"],
    "additionalProperties": False,
}


def recent(store: Store, now: datetime) -> list[Any]:
    with store.connect() as conn:
        return list(conn.execute(
            "SELECT id, source, title, summary, published FROM article WHERE published >= ? "
            "ORDER BY published DESC, id LIMIT ?", ((now - WINDOW).isoformat(), MAX_ARTICLES)))


def _line(n: int, row: Any) -> str:
    first = " ".join((row["summary"] or "").split())[:LINE_CHARS]
    return f"{n}. [{row['source']}] {row['title']}" + (f" | {first}" if first else "")


def parse(answer: str, ids: list[str]) -> list[dict[str, Any]]:
    """The stories by article id: unknown or repeated numbers are dropped."""
    seen: set[int] = set()
    stories = []
    for story in json.loads(answer).get("stories") or []:
        numbers = []
        for n in story.get("articles") or []:
            if isinstance(n, int) and 1 <= n <= len(ids) and n not in seen:
                seen.add(n)
                numbers.append(n)
        if not numbers:
            continue
        summary = " ".join(str(story.get("summary") or "").split())[:SUMMARY_MAX]
        stories.append({"ids": [ids[n - 1] for n in numbers],
                        "summary": summary if len(numbers) > 1 and summary else None})
    return stories


async def group(cfg: dict[str, Any], store: Store, now: datetime | None = None,
                claude: ai.ClientFactory | None = None) -> dict[str, Any] | None:
    """Group the recent articles and keep the stories; None when there is no answer."""
    now = now or datetime.now(UTC)
    rows = recent(store, now)
    if len(rows) < 2:
        return None
    prompt = "Articles:\n" + "\n".join(_line(n, r) for n, r in enumerate(rows, 1))
    answer = await ai.ask(cfg, store, feature=FEATURE, model=ai.SCHEDULED_MODEL, system=SYSTEM,
                          prompt=prompt, max_tokens=4096, schema=SCHEMA, now=now, client=claude)
    if answer is None:
        return None
    try:
        stories = parse(answer, [r["id"] for r in rows])
    except (json.JSONDecodeError, AttributeError):
        log.warning("stories: the answer is not the expected JSON")
        return None
    kept = {"as_of": now.isoformat(), "stories": stories}
    store.put_cache(CACHE_KEY, kept)
    return kept


def fresh(cfg: dict[str, Any], store: Store, now: datetime) -> list[dict[str, Any]] | None:
    """The last grouping, while the feature is on and it is recent enough."""
    if not ai.settings(cfg)["enabled"] or not ai.switches(store).get(FEATURE):
        return None
    kept = store.get_cache(CACHE_KEY) or {}
    if not kept.get("as_of") or now - datetime.fromisoformat(kept["as_of"]) > FRESH:
        return None
    return kept.get("stories") or None
