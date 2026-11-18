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

from apscheduler.events import (
    EVENT_JOB_ERROR,
    EVENT_JOB_EXECUTED,
    EVENT_JOB_MISSED,
    JobEvent,
)
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from . import briefing, config, pinned, reminders
from .alerts import core as alerts_core
from .alerts import rules as alert_rules
from .news import headlines, stories
from .portfolio import indices, weeks
from .portfolio import report as portfolio_report
from .sources import (
    adguard,
    agenda,
    air,
    apple,
    backups,
    birthdays,
    container_stats,
    countdown,
    db_copy,
    docker,
    dumps,
    exposure,
    feeds,
    forecast,
    ghostfolio,
    github,
    github_mirror,
    hue,
    incoming,
    laundry,
    media_overview,
    media_status,
    my_sites,
    nas,
    ns,
    outside_services,
    photo,
    pipelines,
    radar,
    runna,
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
FORECAST_INTERVAL_SECONDS = 1800  # Open-Meteo's models update hourly
WEATHER_INTERVAL_SECONDS = 300  # Buienradar's rain forecast moves in 5-minute steps
EXPOSURE_INTERVAL_SECONDS = 6 * 3600  # a handful of Cloudflare API calls
OUTSIDE_INTERVAL_SECONDS = 300  # status pages; incidents move in minutes
SITES_INTERVAL_SECONDS = 60  # Kuma beats once a minute; 100 kept, so no gaps
LIGHTS_INTERVAL_SECONDS = 60  # two local calls; the event stream does the rest
APPLE_INTERVAL_SECONDS = 60  # local unicast queries, a fraction of a second per device
LAUNDRY_INTERVAL_SECONDS = 60  # one signed status call; the token is reused
PIPELINES_INTERVAL_SECONDS = 15  # a running pipeline moves fast; idle repos are asked once a minute
DNS_INTERVAL_SECONDS = 60  # two local calls to AdGuard Home
AIR_INTERVAL_SECONDS = 60  # one local WebSocket call; the Matter server keeps the sensor subscribed
CALENDAR_INTERVAL_SECONDS = 300  # feeds at most every 15 min (agenda.FEED_EVERY)
COUNTDOWN_INTERVAL_SECONDS = 3600
BIRTHDAYS_INTERVAL_SECONDS = 6 * 3600  # the week is worked out when asked
RADAR_INTERVAL_SECONDS = 300  # Buienradar's frames come every 5 minutes
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


# The last outcome of each job (the MCP `job_status` tool, plan.md M34), in memory only:
# by job id when it ran (the scheduler's events), by cache key whether its refresh worked
# (`_run` catches its failures, so the scheduler sees those as runs that went fine).
RUNS: dict[str, dict[str, Any]] = {}
REFRESHES: dict[str, dict[str, Any]] = {}


def _ran(event: JobEvent) -> None:
    error = getattr(event, "exception", None)
    RUNS[event.job_id] = {"at": datetime.now(UTC), "missed": event.code == EVENT_JOB_MISSED,
                          "error": type(error).__name__ if error else None}


async def _run(store: Store, key: str, job: Callable[[], Awaitable[Any]]) -> None:
    try:
        result = await job()
        store.put_cache(key, result.model_dump(mode="json"))
        REFRESHES[key] = {"at": datetime.now(UTC), "ok": True, "error": None}
    except Exception as exc:
        log.exception("%s refresh failed; serving cached payload as stale", key)
        mark_stale(store, key)
        # The class only: a message can carry a URL with a key in it.
        REFRESHES[key] = {"at": datetime.now(UTC), "ok": False, "error": type(exc).__name__}


async def _stories(cfg: dict[str, Any], store: Store) -> None:
    try:
        await stories.group(cfg, store)
    except Exception:
        log.exception("grouping the headlines failed")


async def _briefing(cfg: dict[str, Any], store: Store) -> None:
    try:
        await briefing.run(cfg, store)
    except Exception:
        log.exception("morning digest failed")


def _at(text: str) -> dict[str, int]:
    """A daily "HH:MM" as a cron trigger's hour and minute."""
    hour, minute = (int(part) for part in text.split(":"))
    return {"hour": hour, "minute": minute}


def build(cfg: dict[str, Any], store: Store) -> AsyncIOScheduler:
    # APScheduler's defaults: one run of a job at a time, missed runs folded into one.
    scheduler = AsyncIOScheduler(timezone=config.zone(cfg).key)
    scheduler.add_listener(_ran, EVENT_JOB_EXECUTED | EVENT_JOB_ERROR | EVENT_JOB_MISSED)

    def refresh(job_id: str, key: str, collect: Callable[[], Awaitable[Any]],
                trigger: str = "interval", **when: Any) -> None:
        """A job that caches what `collect` returns under `key` (see `_run`).

        An interval refresh is added paused: main.py runs them all once at startup, which
        starts their interval.
        """
        if trigger == "interval":
            when.setdefault("next_run_time", None)
        scheduler.add_job(_run, trigger, args=[store, key, collect], id=job_id, **when)

    refresh("nas", "nas", lambda: nas.collect(cfg, store), seconds=NAS_INTERVAL_SECONDS)
    refresh("containers", "containers", lambda: docker.collect(cfg),
            seconds=CONTAINERS_INTERVAL_SECONDS)
    refresh("docker", "docker", lambda: container_stats.collect(cfg, store),
            seconds=DOCKER_INTERVAL_SECONDS)
    refresh("widgets", "widgets", lambda: widgets.collect(cfg, store),
            seconds=WIDGETS_INTERVAL_SECONDS)
    refresh("repos", "repos", lambda: github.collect(cfg, store), seconds=REPOS_INTERVAL_SECONDS)
    refresh("backups", "backups", lambda: backups.collect(cfg), seconds=BACKUPS_INTERVAL_SECONDS)
    refresh("dumps", dumps.CACHE_KEY, lambda: dumps.collect(cfg, store),
            seconds=BACKUPS_INTERVAL_SECONDS)
    refresh("incoming", incoming.CACHE_KEY, lambda: incoming.collect(cfg),
            seconds=BACKUPS_INTERVAL_SECONDS)
    refresh("hosts", "hosts", lambda: tailscale.collect(cfg), seconds=HOSTS_INTERVAL_SECONDS)
    refresh("tailnet", tailscale.TAILNET_CACHE_KEY, lambda: tailscale.collect_tailnet(cfg),
            seconds=TAILNET_INTERVAL_SECONDS)

    if hue.settings(cfg)["enabled"]:
        # A full read; the event stream (hue.listen) keeps it live in between.
        refresh("lights", hue.CACHE_KEY, lambda: hue.collect(cfg),
                seconds=LIGHTS_INTERVAL_SECONDS)
    if apple.settings(cfg)["enabled"]:
        refresh("apple", apple.CACHE_KEY, lambda: apple.collect(cfg, store),
                seconds=APPLE_INTERVAL_SECONDS)
    if pipelines.settings(cfg)["enabled"]:
        refresh("pipelines", pipelines.CACHE_KEY, lambda: pipelines.collect(cfg, store),
                seconds=PIPELINES_INTERVAL_SECONDS)
    if adguard.settings(cfg)["enabled"]:
        refresh("dns", adguard.CACHE_KEY, lambda: adguard.collect(cfg, store),
                seconds=DNS_INTERVAL_SECONDS)
    if air.settings(cfg)["enabled"]:
        refresh("air", air.CACHE_KEY, lambda: air.collect(cfg, store),
                seconds=AIR_INTERVAL_SECONDS)
    if laundry.settings(cfg)["enabled"]:
        refresh("laundry", laundry.CACHE_KEY, lambda: laundry.collect(cfg, store),
                seconds=LAUNDRY_INTERVAL_SECONDS)
    if agenda.settings(cfg)["enabled"]:
        refresh("calendar", agenda.CACHE_KEY, lambda: agenda.collect(cfg, store),
                seconds=CALENDAR_INTERVAL_SECONDS)
        # The countdowns (plan.md M27, K): a year ahead, so hourly is plenty.
        refresh("countdown", countdown.CACHE_KEY, lambda: countdown.collect(cfg, store),
                seconds=COUNTDOWN_INTERVAL_SECONDS)
    if birthdays.settings(cfg)["enabled"]:
        # The contacts' birthdays (plan.md M32), read every 6 hours.
        refresh("birthdays", birthdays.CACHE_KEY, lambda: birthdays.collect(cfg, store),
                seconds=BIRTHDAYS_INTERVAL_SECONDS)
    if runna.settings(cfg)["enabled"]:
        # Runna's plan (plan.md M28): hourly is plenty for a training plan.
        refresh("runna", runna.CACHE_KEY, lambda: runna.collect(cfg, store),
                seconds=COUNTDOWN_INTERVAL_SECONDS)
    if weather.settings(cfg)["enabled"]:
        # The rain radar (plan.md M27, I): only fetched while rain is expected.
        refresh("radar", radar.CACHE_KEY, lambda: radar.collect(cfg, store),
                seconds=RADAR_INTERVAL_SECONDS)
    if photo.settings(cfg)["enabled"]:
        # The photo of the day (plan.md M27, E): each morning, and at start-up (the picture
        # is kept in memory only). The startup run in main.py only covers interval jobs.
        refresh("photo", photo.CACHE_KEY, lambda: photo.collect(cfg, store), "cron",
                hour=6, minute=5, next_run_time=datetime.now(UTC))
    if my_sites.settings(cfg, store)["enabled"]:
        refresh("sites", my_sites.CACHE_KEY, lambda: my_sites.collect(cfg, store),
                seconds=SITES_INTERVAL_SECONDS)
    if media_overview.settings(cfg, store)["enabled"]:
        refresh("media-overview", media_overview.CACHE_KEY,
                lambda: media_overview.collect(cfg, store), seconds=OVERVIEW_INTERVAL_SECONDS)
    if media_status.settings(cfg, store)["enabled"]:
        refresh("media", media_status.CACHE_KEY, lambda: media_status.collect(cfg, store),
                seconds=MEDIA_INTERVAL_SECONDS)
    if ns.settings(cfg)["enabled"]:
        refresh("train", ns.CACHE_KEY, lambda: ns.collect(cfg, store),
                seconds=TRAIN_INTERVAL_SECONDS)

    refresh("news", "news", lambda: feeds.collect(cfg, store), seconds=NEWS_INTERVAL_SECONDS)
    # From the articles the news job stored; a picture is fetched once per story.
    refresh("headlines", headlines.CACHE_KEY, lambda: headlines.collect(store, cfg=cfg),
            seconds=HEADLINES_INTERVAL_SECONDS)
    refresh("portfolio", "portfolio",
            lambda: ghostfolio.collect(cfg, cfg.get("currency", "EUR"), store),
            seconds=PORTFOLIO_INTERVAL_SECONDS)
    refresh("indices", "indices", lambda: indices.collect(cfg), seconds=PORTFOLIO_INTERVAL_SECONDS)
    # A week of prices per holding, for the panel's Stock screen and the week card.
    refresh("stock-weeks", weeks.CACHE_KEY, lambda: weeks.collect(store),
            seconds=PORTFOLIO_INTERVAL_SECONDS)
    refresh("spotlight", "spotlight", lambda: spotlight.collect(cfg, store),
            seconds=PORTFOLIO_INTERVAL_SECONDS)

    # The nightly git mirror of the GitHub repos, before the 03:00 Hetzner
    # backup. Right after startup too when a night was missed (hub down).
    mirror = github_mirror.settings(cfg)
    if mirror["enabled"]:
        now = datetime.now(UTC)
        first = (
            {"next_run_time": now + MIRROR_STARTUP_DELAY}
            if github_mirror.overdue(cfg, store, now) else {}
        )
        refresh("github-mirror", github_mirror.CACHE_KEY,
                lambda: github_mirror.collect(cfg, store), "cron",
                **_at(mirror["at"]), misfire_grace_time=3600, **first)

    if weather.settings(cfg)["enabled"]:
        # The day view's hourly forecast (Open-Meteo), for the same place.
        refresh("forecast", forecast.CACHE_KEY, lambda: forecast.collect(cfg),
                seconds=FORECAST_INTERVAL_SECONDS)
        refresh("weather", weather.CACHE_KEY, lambda: weather.collect(cfg),
                seconds=WEATHER_INTERVAL_SECONDS)
    if outside_services.settings(cfg):
        refresh("outside-services", outside_services.CACHE_KEY,
                lambda: outside_services.collect(cfg, store), seconds=OUTSIDE_INTERVAL_SECONDS)
    # What of the house is public, from Cloudflare's view.
    if exposure.settings(cfg)["enabled"]:
        refresh("exposure", exposure.CACHE_KEY, lambda: exposure.collect(cfg, store),
                seconds=EXPOSURE_INTERVAL_SECONDS)
    # The UPS over NUT, and one report per finished power cut.
    if ups.settings(cfg)["enabled"]:
        refresh("ups", ups.CACHE_KEY, lambda: ups.collect(cfg, store),
                seconds=UPS_INTERVAL_SECONDS)
        scheduler.add_job(ups.report_outages, "interval", minutes=5, args=[store, cfg],
                          id="ups-report")

    # The morning digest (M26): weekdays, written by Claude when switched on.
    scheduler.add_job(_briefing, "cron", day_of_week="mon-fri", **_at(briefing.AT),
                      args=[cfg, store], id="briefing", misfire_grace_time=1800)
    # Headlines, one story per event (M26): grouped hourly, read by the headlines job.
    scheduler.add_job(_stories, "cron", hour=stories.HOURS, minute=3, args=[cfg, store],
                      id="stories", misfire_grace_time=1800)
    # Pinned images: a warning before an update that breaks (M26, with update notes).
    refresh("pinned", pinned.CACHE_KEY, lambda: pinned.collect(cfg, store), "cron",
            **_at(pinned.CHECK_AT), misfire_grace_time=3600)
    # A consistent copy of the hub's own database for the 03:00 Hetzner backup.
    refresh("db-copy", db_copy.CACHE_KEY, lambda: db_copy.collect(store), "cron",
            **_at(db_copy.settings(cfg)["at"]), misfire_grace_time=600)

    # The hub's own alert rules.
    scheduler.add_job(alert_rules.check, "interval", seconds=60, args=[cfg, store],
                      id="alert-rules")
    # The reminders' ntfy messages (plan.md M32): each goes out in the minute it is due.
    scheduler.add_job(reminders.send_due, "interval", seconds=60, args=[cfg, store],
                      id="reminders")
    # The portfolio report to the Portfolio chat (stock-bot's job before).
    if portfolio_report.settings(cfg)["enabled"]:
        scheduler.add_job(portfolio_report.send, portfolio_report.trigger(cfg), args=[store, cfg],
                          id="portfolio-report", misfire_grace_time=600)
    # After quiet hours, the held messages go out as one digest per chat.
    scheduler.add_job(alerts_core.send_digests, "interval", minutes=5, args=[store, cfg],
                      id="alert-digest")
    return scheduler
