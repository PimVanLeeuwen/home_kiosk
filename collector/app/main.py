"""FastAPI app exposing the four dashboard endpoints.

No auth — LAN only, per docs/kiosk-build-spec.md §11. Endpoints never raise on a source failure:
they serve the last-good cached payload, flagged stale. The only non-200 case is
a cold start with nothing cached yet, which the frontend renders with its
"collector unreachable" fallback.
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from typing import Any

from apscheduler.triggers.interval import IntervalTrigger
from fastapi import Depends, FastAPI
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, HttpUrl

from . import (
    config,
    desk_api,
    desk_boards,
    desk_headlines,
    exposure_api,
    lights_api,
    music_api,
    scheduler,
    settings_api,
)
from .alerts import api as alerts_api
from .alerts import bot as alert_bot
from .alerts import core as alerts_core
from .alerts import rules as alert_rules
from .models import ContainerUpdate
from .news import api as news_api
from .news import headlines
from .news import store as news_store
from .portfolio import api as portfolio_api
from .portfolio import degiro_import
from .security import same_origin_json
from .sources import (
    agenda,
    apple,
    apple_tv,
    container_stats,
    exposure,
    feeds,
    github_mirror,
    hue,
    laundry,
    media_overview,
    media_status,
    music,
    my_sites,
    ns,
    outside_services,
    readeck,
    spotify,
    tailscale,
    ups,
    weather,
)
from .sources import nas as nas_source
from .sources import services as service_catalog
from .store import Store

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
log = logging.getLogger(__name__)
# httpx logs every request URL at INFO, and SABnzbd only takes its API key as a
# query parameter: keep URLs out of the container log (Dozzle shows it to the LAN).
logging.getLogger("httpx").setLevel(logging.WARNING)

CACHE_KEYS = {
    "portfolio": "portfolio",
    "spotlight": "spotlight",
    "news": "news",
    "nas": "nas",
}


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.config = config.load()
    app.state.store = Store(app.state.config.get("database", "./data/collector.db"))
    log.info(service_catalog.prepare(app.state.store, app.state.config))
    alerts_core.ensure_tables(app.state.store)
    alert_rules.ensure_tables(app.state.store)
    news_store.ensure_tables(app.state.store)
    degiro_import.ensure_tables(app.state.store)
    ups.ensure_tables(app.state.store)
    my_sites.ensure_tables(app.state.store)
    agenda.ensure_tables(app.state.store)
    desk_boards.ensure_tables(app.state.store)
    desk_headlines.ensure_tables(app.state.store)
    apple.ensure_tables(app.state.store)
    laundry.ensure_tables(app.state.store)
    spotify.ensure_tables(app.state.store)
    # A favourite can wake the living room Apple TV and open Spotify on it.
    music.wake = apple_tv.wake_spotify
    if news_store.seed(app.state.store, app.state.config):
        log.info("feed list seeded from config.yaml")

    # Unset ${VAR} references expand to "", which would otherwise only surface
    # as a failed save long after startup.
    if not (app.state.config.get("readeck") or {}).get("api_token"):
        log.warning("READECK_TOKEN is not set — tap-to-save will fail until it is")

    app.state.scheduler = scheduler.build(app.state.config, app.state.store)
    app.state.scheduler.start()
    # Populate the cache immediately rather than leaving the screen blank for a
    # full interval after a restart.
    # Only the refreshes: a timed job like the portfolio report keeps its schedule.
    for job in app.state.scheduler.get_jobs():
        if isinstance(job.trigger, IntervalTrigger):
            job.modify(next_run_time=datetime.now(UTC))

    # Telegram commands: long polling in the background (off without a token).
    bot_task = asyncio.create_task(alert_bot.run(app.state.store, app.state.config))
    # The Hue Bridge's event stream keeps the lights live between full reads.
    tasks = [bot_task]
    if hue.settings(app.state.config)["enabled"]:
        tasks.append(asyncio.create_task(hue.listen(app.state.config, app.state.store)))

    try:
        yield
    finally:
        for task in tasks:
            task.cancel()
        app.state.scheduler.shutdown(wait=False)


app = FastAPI(title="Desk Dashboard Collector", version="0.1.0", lifespan=lifespan)

# No CORS: the hub, the kiosk and the Vite dev server all reach the API on the
# same origin. Allowing any origin would let other websites call the write
# endpoints; see security.py.
app.include_router(settings_api.router)
app.include_router(exposure_api.router)
app.include_router(lights_api.router)
app.include_router(music_api.router)
app.include_router(desk_api.router)
app.include_router(alerts_api.router)
app.include_router(news_api.router)
app.include_router(portfolio_api.router)


def _serve(key: str) -> Any:
    payload = app.state.store.get_cache(key)
    if payload is None:
        return JSONResponse(
            status_code=503,
            content={"detail": f"no {key} data collected yet"},
        )
    return payload


@app.get("/health")
@app.get("/api/health")
def health() -> dict[str, str]:
    """Liveness probe.

    Also exposed under /api so the dashboard can reach it through Caddy's
    `/api/*` proxy rule. The frontend needs a signal that distinguishes "the
    collector is down" from "something answered" — a 404 from a static server or
    a 502 from the proxy are both HTTP responses, so status codes alone cannot
    tell the two apart.
    """
    return {"status": "ok"}


@app.get("/api/portfolio")
def portfolio() -> Any:
    return _serve(CACHE_KEYS["portfolio"])


@app.get("/api/spotlight")
def spotlight() -> Any:
    return _serve(CACHE_KEYS["spotlight"])


@app.get("/api/news")
def news() -> Any:
    return _serve(CACHE_KEYS["news"])


@app.get("/api/news/headlines")
def news_headlines() -> Any:
    """The newest story of each group, the lead first (the Headlines screen)."""
    return _serve(headlines.CACHE_KEY)


@app.get("/api/news/full")
def news_full() -> Any:
    """Everything the feeds returned, newest first — for reading on a phone.

    The kiosk view shows a handful of interleaved headlines per group, which is
    right on a screen you glance at and far too thin to read. Written by the
    same job from the same fetch, so this costs no extra requests.
    """
    return _serve(feeds.FULL_CACHE_KEY)


@app.get("/api/nas")
def nas() -> Any:
    return _serve(CACHE_KEYS["nas"])


@app.get("/api/hosts")
def hosts() -> Any:
    return _serve("hosts")


@app.get("/api/laundry")
def laundry_status() -> Any:
    """The washer and dryer: running, done, paused or with an error."""
    return _serve(laundry.CACHE_KEY)


@app.get("/api/apple")
def apple_devices() -> Any:
    """The Apple TVs and HomePods per room: online, Thread and what plays."""
    return _serve(apple.CACHE_KEY)


@app.get("/api/apple/artwork/{room}")
def apple_artwork(room: str) -> Response:
    """The stored artwork of what plays in a room; nothing is fetched here."""
    data = apple.artwork(app.state.store, room)
    if not data:
        return JSONResponse(status_code=404, content={"detail": "No artwork."})
    return Response(data, media_type="image/webp", headers={
        "Cache-Control": "private, max-age=300", "X-Content-Type-Options": "nosniff"})


@app.get("/api/calendar")
def calendar_today() -> Any:
    """Today's events from the calendars switched on in Settings."""
    return _serve(agenda.CACHE_KEY)


@app.get("/api/sites")
def sites() -> Any:
    """The owner's websites: up now and 30 days of uptime, from Uptime Kuma."""
    return _serve(my_sites.CACHE_KEY)


@app.get("/api/media")
def media() -> Any:
    """Downloads, missing episodes and what airs next, from Sonarr and Radarr."""
    return _serve(media_status.CACHE_KEY)


@app.get("/api/media/overview")
def media_overview_status() -> Any:
    """Who watched how much, the library and requests, from Tracearr and Jellyseerr."""
    return _serve(media_overview.CACHE_KEY)


@app.get("/api/media/posters/{source}/{item_id}")
async def media_poster(source: str, item_id: int) -> Response:
    """A poster of an item in the current Media answer, through the hub."""
    try:
        data, kind = await media_status.poster(app.state.config, app.state.store, source, item_id)
    except LookupError:
        return JSONResponse(status_code=404, content={"detail": "No such poster."})
    except Exception as exc:
        log.warning("media poster failed: %s", type(exc).__name__)
        return JSONResponse(status_code=502, content={"detail": "The poster could not be loaded."})
    return Response(data, media_type=kind, headers={"Cache-Control": "private, max-age=86400"})


@app.get("/api/train")
def train() -> Any:
    """The weekday morning train; 503 until the first check after startup."""
    return _serve(ns.CACHE_KEY)


@app.get("/api/tailnet")
def tailnet() -> Any:
    return _serve(tailscale.TAILNET_CACHE_KEY)


@app.get("/api/containers")
def containers() -> Any:
    return _serve("containers")


@app.get("/api/nas/history")
def nas_history() -> Any:
    """CPU, memory, temperature and network over the last 24 hours."""
    since = datetime.now(UTC) - timedelta(hours=24)
    return nas_source.history(app.state.store.recent_nas_samples(since))


@app.get("/api/github-mirror")
def github_mirror_status() -> Any:
    return github_mirror.current(app.state.config, app.state.store)


@app.get("/api/backups")
def backups() -> Any:
    return _serve("backups")


@app.get("/api/exposure")
def exposure_audit() -> Any:
    return _serve(exposure.CACHE_KEY)


@app.get("/api/weather")
def weather_now() -> Any:
    return _serve(weather.CACHE_KEY)


@app.get("/api/outside-services")
def outside_services_status() -> Any:
    return _serve(outside_services.CACHE_KEY)


@app.get("/api/ups")
def ups_status() -> Any:
    return _serve(ups.CACHE_KEY)


@app.get("/api/database-dumps")
def database_dumps() -> Any:
    return _serve("dumps")


@app.get("/api/docker")
def docker_overview() -> Any:
    return _serve("docker")


@app.get("/api/docker/sparklines")
def docker_sparklines() -> Any:
    since = datetime.now(UTC) - timedelta(hours=24)
    return container_stats.sparklines(app.state.store.all_container_samples(since))


@app.get("/api/docker/history/{name}")
def docker_history(name: str) -> Any:
    """One container's CPU and memory over the last 24 hours, in 10-minute buckets."""
    since = datetime.now(UTC) - timedelta(hours=24)
    return container_stats.history(app.state.store.container_samples(name, since))


@app.get("/api/docker/updates")
def docker_updates() -> Any:
    """Image updates noticed so far, newest first."""
    return [
        ContainerUpdate(
            at=r["ts"], name=r["name"], image=r["image"],
            old_image_id=r["old_image_id"], new_image_id=r["new_image_id"],
        )
        for r in app.state.store.container_updates()
    ]


@app.get("/api/repos")
def repos() -> Any:
    return _serve("repos")


@app.get("/api/services")
def services() -> Any:
    """The service catalog with a status per service. Always 200: the catalog
    is local, and without a container list every status reads "unknown"."""
    store = app.state.store
    return service_catalog.build(
        store.list_services(), store.get_cache("containers"), store.get_cache("widgets")
    )


class SaveRequest(BaseModel):
    url: HttpUrl
    title: str | None = None


@app.post("/api/save", dependencies=[Depends(same_origin_json)])
async def save(req: SaveRequest) -> Any:
    """Queue an article in Readeck.

    Errors are returned as 502 with a short human message: the screen shows it
    verbatim, so it has to read as a sentence rather than a stack trace.
    """
    try:
        bookmark_id = await readeck.save(app.state.config, str(req.url), req.title)
    except readeck.SaveError as exc:
        return JSONResponse(status_code=502, content={"detail": str(exc)})
    return {"saved": True, "bookmark_id": bookmark_id}
