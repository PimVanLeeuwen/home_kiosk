"""FastAPI app exposing the four dashboard endpoints.

No auth — LAN only, per plan.md §11. Endpoints never raise on a source failure:
they serve the last-good cached payload, flagged stale. The only non-200 case is
a cold start with nothing cached yet, which the frontend renders with its
"collector unreachable" fallback.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from . import config
from .store import Store

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
    yield


app = FastAPI(title="Desk Dashboard Collector", version="0.1.0", lifespan=lifespan)

# LAN-only appliance; the dashboard may be served from a different port during
# development, so origin checks would only get in the way.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
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
def health() -> dict[str, str]:
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


@app.get("/api/nas")
def nas() -> Any:
    return _serve(CACHE_KEYS["nas"])
