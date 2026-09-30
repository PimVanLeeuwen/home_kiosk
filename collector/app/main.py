"""FastAPI app exposing the four dashboard endpoints.

No auth — LAN only, per docs/kiosk-build-spec.md §11. Endpoints never raise on a source failure:
they serve the last-good cached payload, flagged stale. The only non-200 case is
a cold start with nothing cached yet, which the frontend renders with its
"collector unreachable" fallback.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, HttpUrl

from . import config, scheduler
from .sources import feeds, readeck
from .store import Store

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
log = logging.getLogger(__name__)

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

# LAN-only appliance; the dashboard may be served from a different port during
# development, so origin checks would only get in the way.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


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


class SaveRequest(BaseModel):
    url: HttpUrl
    title: str | None = None


@app.post("/api/save")
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
