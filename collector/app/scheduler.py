"""APScheduler jobs on the cadences in docs/kiosk-build-spec.md §5.

Each job refreshes one endpoint's cached payload. A job that raises leaves the
previous payload in place and flags it stale, so the screen keeps showing the
last good data instead of an error.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import Any

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from .sources import (
    container_stats,
    docker,
    feeds,
    ghostfolio,
    github,
    nas,
    spotlight,
    tailscale,
    widgets,
)
from .store import Store

log = logging.getLogger(__name__)

NAS_INTERVAL_SECONDS = 60
CONTAINERS_INTERVAL_SECONDS = 30  # status dots on the Services page
DOCKER_INTERVAL_SECONDS = 60  # per-container load and image updates
WIDGETS_INTERVAL_SECONDS = 60  # tile stats
REPOS_INTERVAL_SECONDS = 1800  # GitHub repos; well inside the API limits
HOSTS_INTERVAL_SECONDS = 600  # the tailnet name practically never changes
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
        seconds=CONTAINERS_INTERVAL_SECONDS,
        args=[store, "containers", lambda: docker.collect(cfg)],
        id="containers",
        next_run_time=None,
        max_instances=1,
        coalesce=True,
    )

    scheduler.add_job(
        _run,
        "interval",
        seconds=DOCKER_INTERVAL_SECONDS,
        args=[store, "docker", lambda: container_stats.collect(cfg, store)],
        id="docker",
        next_run_time=None,
        max_instances=1,
        coalesce=True,
    )

    scheduler.add_job(
        _run,
        "interval",
        seconds=WIDGETS_INTERVAL_SECONDS,
        args=[store, "widgets", lambda: widgets.collect(cfg, store)],
        id="widgets",
        next_run_time=None,
        max_instances=1,
        coalesce=True,
    )

    scheduler.add_job(
        _run,
        "interval",
        seconds=REPOS_INTERVAL_SECONDS,
        args=[store, "repos", lambda: github.collect(cfg, store)],
        id="repos",
        next_run_time=None,
        max_instances=1,
        coalesce=True,
    )

    scheduler.add_job(
        _run,
        "interval",
        seconds=HOSTS_INTERVAL_SECONDS,
        args=[store, "hosts", lambda: tailscale.collect(cfg)],
        id="hosts",
        next_run_time=None,
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
