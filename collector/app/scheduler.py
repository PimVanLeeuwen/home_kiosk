"""APScheduler jobs on the cadences in docs/kiosk-build-spec.md §5.

Each job refreshes one endpoint's cached payload. A job that raises leaves the
previous payload in place and flags it stale, so the screen keeps showing the
last good data instead of an error.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from typing import Any

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from .alerts import core as alerts_core
from .alerts import rules as alert_rules
from .news import headlines
from .portfolio import indices
from .portfolio import report as portfolio_report
from .sources import (
    agenda,
    apple,
    backups,
    container_stats,
    db_copy,
    docker,
    dumps,
    exposure,
    feeds,
    ghostfolio,
    github,
    github_mirror,
    hue,
    laundry,
    media_overview,
    media_status,
    my_sites,
    nas,
    ns,
    outside_services,
    spotlight,
    tailscale,
    ups,
    weather,
    widgets,
)
from .store import Store

log = logging.getLogger(__name__)

NAS_INTERVAL_SECONDS = 60
CONTAINERS_INTERVAL_SECONDS = 30  # status dots on the Services page
DOCKER_INTERVAL_SECONDS = 60  # per-container load and image updates
WIDGETS_INTERVAL_SECONDS = 60  # tile stats
REPOS_INTERVAL_SECONDS = 1800  # GitHub repos; well inside the API limits
BACKUPS_INTERVAL_SECONDS = 300  # the run file changes once a day
HOSTS_INTERVAL_SECONDS = 600  # the tailnet name practically never changes
TAILNET_INTERVAL_SECONDS = 60  # devices come and go; a local socket call
NEWS_INTERVAL_SECONDS = 600       # §5: feeds every 10 minutes
HEADLINES_INTERVAL_SECONDS = 300  # local reads; a new story's picture is fetched once
PORTFOLIO_INTERVAL_SECONDS = 900  # §5: portfolio every 15 minutes
WEATHER_INTERVAL_SECONDS = 300  # Buienradar's rain forecast moves in 5-minute steps
EXPOSURE_INTERVAL_SECONDS = 6 * 3600  # a handful of Cloudflare API calls
OUTSIDE_INTERVAL_SECONDS = 300  # status pages; incidents move in minutes
SITES_INTERVAL_SECONDS = 60  # Kuma beats once a minute; 100 kept, so no gaps
LIGHTS_INTERVAL_SECONDS = 60  # two local calls; the event stream does the rest
APPLE_INTERVAL_SECONDS = 60  # local unicast queries, a fraction of a second per device
LAUNDRY_INTERVAL_SECONDS = 60  # one signed status call; the token is reused
CALENDAR_INTERVAL_SECONDS = 300  # feeds at most every 15 min (agenda.FEED_EVERY)
MEDIA_INTERVAL_SECONDS = 60  # local calls to Sonarr and Radarr
OVERVIEW_INTERVAL_SECONDS = 300  # watch stats and library counts move slowly
TRAIN_INTERVAL_SECONDS = 120  # calls NS only between the watch start and departure
UPS_INTERVAL_SECONDS = 15  # outages are timed from these readings
MIRROR_STARTUP_DELAY = timedelta(minutes=2)  # let the startup refreshes go first


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
        seconds=BACKUPS_INTERVAL_SECONDS,
        args=[store, "backups", lambda: backups.collect(cfg)],
        id="backups",
        next_run_time=None,
        max_instances=1,
        coalesce=True,
    )

    scheduler.add_job(
        _run,
        "interval",
        seconds=BACKUPS_INTERVAL_SECONDS,
        args=[store, dumps.CACHE_KEY, lambda: dumps.collect(cfg, store)],
        id="dumps",
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
        seconds=TAILNET_INTERVAL_SECONDS,
        args=[store, tailscale.TAILNET_CACHE_KEY, lambda: tailscale.collect_tailnet(cfg)],
        id="tailnet",
        next_run_time=None,
        max_instances=1,
        coalesce=True,
    )

    if hue.settings(cfg)["enabled"]:
        # A full read; the event stream (hue.listen) keeps it live in between.
        scheduler.add_job(
            _run,
            "interval",
            seconds=LIGHTS_INTERVAL_SECONDS,
            args=[store, hue.CACHE_KEY, lambda: hue.collect(cfg)],
            id="lights",
            next_run_time=None,
            max_instances=1,
            coalesce=True,
        )

    if apple.settings(cfg)["enabled"]:
        scheduler.add_job(
            _run,
            "interval",
            seconds=APPLE_INTERVAL_SECONDS,
            args=[store, apple.CACHE_KEY, lambda: apple.collect(cfg, store)],
            id="apple",
            next_run_time=None,
            max_instances=1,
            coalesce=True,
        )

    if laundry.settings(cfg)["enabled"]:
        scheduler.add_job(
            _run,
            "interval",
            seconds=LAUNDRY_INTERVAL_SECONDS,
            args=[store, laundry.CACHE_KEY, lambda: laundry.collect(cfg, store)],
            id="laundry",
            next_run_time=None,
            max_instances=1,
            coalesce=True,
        )

    if agenda.settings(cfg)["enabled"]:
        scheduler.add_job(
            _run,
            "interval",
            seconds=CALENDAR_INTERVAL_SECONDS,
            args=[store, agenda.CACHE_KEY, lambda: agenda.collect(cfg, store)],
            id="calendar",
            next_run_time=None,
            max_instances=1,
            coalesce=True,
        )

    if my_sites.settings(cfg, store)["enabled"]:
        scheduler.add_job(
            _run,
            "interval",
            seconds=SITES_INTERVAL_SECONDS,
            args=[store, my_sites.CACHE_KEY, lambda: my_sites.collect(cfg, store)],
            id="sites",
            next_run_time=None,
            max_instances=1,
            coalesce=True,
        )

    if media_overview.settings(cfg, store)["enabled"]:
        scheduler.add_job(
            _run,
            "interval",
            seconds=OVERVIEW_INTERVAL_SECONDS,
            args=[store, media_overview.CACHE_KEY, lambda: media_overview.collect(cfg, store)],
            id="media-overview",
            next_run_time=None,
            max_instances=1,
            coalesce=True,
        )

    if media_status.settings(cfg, store)["enabled"]:
        scheduler.add_job(
            _run,
            "interval",
            seconds=MEDIA_INTERVAL_SECONDS,
            args=[store, media_status.CACHE_KEY, lambda: media_status.collect(cfg, store)],
            id="media",
            next_run_time=None,
            max_instances=1,
            coalesce=True,
        )

    if ns.settings(cfg)["enabled"]:
        scheduler.add_job(
            _run,
            "interval",
            seconds=TRAIN_INTERVAL_SECONDS,
            args=[store, ns.CACHE_KEY, lambda: ns.collect(cfg, store)],
            id="train",
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

    # From the articles the news job stored; a picture is fetched once per story.
    scheduler.add_job(
        _run,
        "interval",
        seconds=HEADLINES_INTERVAL_SECONDS,
        args=[store, headlines.CACHE_KEY, lambda: headlines.collect(store)],
        id="headlines",
        next_run_time=None,
        max_instances=1,
        coalesce=True,
    )

    scheduler.add_job(
        _run,
        "interval",
        seconds=PORTFOLIO_INTERVAL_SECONDS,
        args=[
            store, "portfolio", lambda: ghostfolio.collect(cfg, cfg.get("currency", "EUR"), store)
        ],
        id="portfolio",
        next_run_time=None,
        max_instances=1,
        coalesce=True,
    )

    scheduler.add_job(
        _run,
        "interval",
        seconds=PORTFOLIO_INTERVAL_SECONDS,
        args=[store, "indices", lambda: indices.collect(cfg)],
        id="indices",
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
    # The nightly git mirror of the GitHub repos, before the 03:00 Hetzner
    # backup. Right after startup too when a night was missed (hub down).
    mirror = github_mirror.settings(cfg)
    if mirror["enabled"]:
        hour, minute = (int(part) for part in mirror["at"].split(":"))
        now = datetime.now(UTC)
        first = (
            {"next_run_time": now + MIRROR_STARTUP_DELAY}
            if github_mirror.overdue(cfg, store, now) else {}
        )
        scheduler.add_job(
            _run,
            "cron",
            hour=hour,
            minute=minute,
            args=[store, github_mirror.CACHE_KEY, lambda: github_mirror.collect(cfg, store)],
            id="github-mirror",
            max_instances=1,
            coalesce=True,
            misfire_grace_time=3600,
            **first,
        )

    if weather.settings(cfg)["enabled"]:
        scheduler.add_job(
            _run,
            "interval",
            seconds=WEATHER_INTERVAL_SECONDS,
            args=[store, weather.CACHE_KEY, lambda: weather.collect(cfg)],
            id="weather",
            next_run_time=None,
            max_instances=1,
            coalesce=True,
        )

    if outside_services.settings(cfg):
        scheduler.add_job(
            _run,
            "interval",
            seconds=OUTSIDE_INTERVAL_SECONDS,
            args=[store, outside_services.CACHE_KEY,
                  lambda: outside_services.collect(cfg, store)],
            id="outside-services",
            next_run_time=None,
            max_instances=1,
            coalesce=True,
        )

    # What of the house is public, from Cloudflare's view.
    if exposure.settings(cfg)["enabled"]:
        scheduler.add_job(
            _run,
            "interval",
            seconds=EXPOSURE_INTERVAL_SECONDS,
            args=[store, exposure.CACHE_KEY, lambda: exposure.collect(cfg, store)],
            id="exposure",
            next_run_time=None,
            max_instances=1,
            coalesce=True,
        )

    # The UPS over NUT, and one report per finished power cut.
    if ups.settings(cfg)["enabled"]:
        scheduler.add_job(
            _run,
            "interval",
            seconds=UPS_INTERVAL_SECONDS,
            args=[store, ups.CACHE_KEY, lambda: ups.collect(cfg, store)],
            id="ups",
            next_run_time=None,
            max_instances=1,
            coalesce=True,
        )
        scheduler.add_job(
            ups.report_outages,
            "interval",
            minutes=5,
            args=[store, cfg],
            id="ups-report",
            max_instances=1,
            coalesce=True,
        )

    # A consistent copy of the hub's own database for the 03:00 Hetzner backup.
    hour, minute = (int(part) for part in db_copy.settings(cfg)["at"].split(":"))
    scheduler.add_job(
        _run,
        "cron",
        hour=hour,
        minute=minute,
        args=[store, db_copy.CACHE_KEY, lambda: db_copy.collect(store)],
        id="db-copy",
        max_instances=1,
        coalesce=True,
        misfire_grace_time=600,
    )

    # The hub's own alert rules.
    scheduler.add_job(
        alert_rules.check,
        "interval",
        seconds=60,
        args=[cfg, store],
        id="alert-rules",
        max_instances=1,
        coalesce=True,
    )

    # The portfolio report to the Portfolio chat (stock-bot's job before).
    if portfolio_report.settings(cfg)["enabled"]:
        scheduler.add_job(
            portfolio_report.send,
            portfolio_report.trigger(cfg),
            args=[store, cfg],
            id="portfolio-report",
            max_instances=1,
            coalesce=True,
            misfire_grace_time=600,
        )

    # After quiet hours, the held messages go out as one digest per chat.
    scheduler.add_job(
        alerts_core.send_digests,
        "interval",
        minutes=5,
        args=[store, cfg],
        id="alert-digest",
        max_instances=1,
        coalesce=True,
    )
    return scheduler
