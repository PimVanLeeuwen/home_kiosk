"""FastAPI app exposing the four dashboard endpoints.

No auth — LAN only, per docs/kiosk-build-spec.md §11. Endpoints never raise on a source failure:
they serve the last-good cached payload, flagged stale. The only non-200 case is
a cold start with nothing cached yet, which the frontend renders with its
"collector unreachable" fallback.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import Depends, FastAPI
from fastapi.responses import JSONResponse
from pydantic import BaseModel, HttpUrl

from . import config, scheduler, settings_api
from .models import ContainerUpdate
from .security import same_origin_json
from .sources import container_stats, feeds, readeck
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

    # Unset ${VAR} references expand to "", which would otherwise only surface
    # as a failed save long after startup.
    if not (app.state.config.get("readeck") or {}).get("api_token"):
        log.warning("READECK_TOKEN is not set — tap-to-save will fail until it is")

    app.state.scheduler = scheduler.build(app.state.config, app.state.store)
    app.state.scheduler.start()
    # Populate the cache immediately rather than leaving the screen blank for a
    # full interval after a restart.
    for job in app.state.scheduler.get_jobs():
        job.modify(next_run_time=datetime.now(UTC))

    try:
        yield
    finally:
        app.state.scheduler.shutdown(wait=False)


app = FastAPI(title="Desk Dashboard Collector", version="0.1.0", lifespan=lifespan)

# No CORS: the hub, the kiosk and the Vite dev server all reach the API on the
# same origin. Allowing any origin would let other websites call the write
# endpoints; see security.py.
app.include_router(settings_api.router)


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


@app.get("/api/containers")
def containers() -> Any:
    return _serve("containers")


@app.get("/api/nas/history")
def nas_history() -> Any:
    """CPU, memory, temperature and network over the last 24 hours."""
    since = datetime.now(UTC) - timedelta(hours=24)
    return nas_source.history(app.state.store.recent_nas_samples(since))


@app.get("/api/backups")
def backups() -> Any:
    return _serve("backups")


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
    """Queue an article in Readeck. The only write path in the project.

    Errors are returned as 502 with a short human message: the screen shows it
    verbatim, so it has to read as a sentence rather than a stack trace.
    """
    try:
        bookmark_id = await readeck.save(app.state.config, str(req.url), req.title)
    except readeck.SaveError as exc:
        return JSONResponse(status_code=502, content={"detail": str(exc)})
    return {"saved": True, "bookmark_id": bookmark_id}
