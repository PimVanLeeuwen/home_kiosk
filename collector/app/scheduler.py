"""APScheduler jobs on the cadences in plan.md §5.

Each job refreshes one endpoint's cached payload. A job that raises leaves the
previous payload in place and flags it stale, so the screen keeps showing the
last good data instead of an error.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import Any

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from .sources import feeds, ghostfolio, nas, spotlight
from .store import Store

log = logging.getLogger(__name__)

NAS_INTERVAL_SECONDS = 60
NEWS_INTERVAL_SECONDS = 600       # §5: feeds every 10 minutes
PORTFOLIO_INTERVAL_SECONDS = 900  # §5: portfolio every 15 minutes


def mark_stale(store: Store, key: str) -> None:
    """Flag the cached payload stale, leaving as_of at the last good fetch."""
    payload = store.get_cache(key)
    if payload and not payload.get("stale"):
        payload["stale"] = True
        store.put_cache(key, payload)


async def _run(store: Store, key: str, job: Callable[[], Awaitable[Any]]) -> None:
    try:
        result = await job()
        store.put_cache(key, result.model_dump(mode="json"))
    except Exception:
        log.exception("%s refresh failed; serving cached payload as stale", key)
        mark_stale(store, key)


def build(cfg: dict[str, Any], store: Store) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone=cfg.get("timezone", "UTC"))

    scheduler.add_job(
        _run,
        "interval",
        seconds=NAS_INTERVAL_SECONDS,
        args=[store, "nas", lambda: nas.collect(cfg, store)],
        id="nas",
        next_run_time=None,  # first run is triggered explicitly at startup
        max_instances=1,
        coalesce=True,
    )

    scheduler.add_job(
        _run,
        "interval",
        seconds=NEWS_INTERVAL_SECONDS,
        args=[store, "news", lambda: feeds.collect(cfg, store)],
        id="news",
        next_run_time=None,
        max_instances=1,
        coalesce=True,
    )

    scheduler.add_job(
        _run,
        "interval",
        seconds=PORTFOLIO_INTERVAL_SECONDS,
        args=[store, "portfolio", lambda: ghostfolio.collect(cfg, cfg.get("currency", "EUR"))],
        id="portfolio",
        next_run_time=None,
        max_instances=1,
        coalesce=True,
    )

    scheduler.add_job(
        _run,
        "interval",
        seconds=PORTFOLIO_INTERVAL_SECONDS,
        args=[store, "spotlight", lambda: spotlight.collect(cfg, store)],
        id="spotlight",
        next_run_time=None,
        max_instances=1,
        coalesce=True,
    )
    return scheduler
