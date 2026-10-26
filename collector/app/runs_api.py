"""Runs (plan.md M28): Health Auto Export on the phone posts workouts here with the hub's runs
key; the hub's pages read them. The phone is not same-origin, so its write is checked by the
key instead (`running.key`, NAS-only `RUNS_KEY`), compared in constant time.
"""

from __future__ import annotations

import hmac
import json
import logging
from datetime import UTC, datetime
from typing import Any
from zoneinfo import ZoneInfo

from fastapi import APIRouter, HTTPException, Request

from . import running
from .sources import runna, runs

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/runs")

MAX_BODY = 200 * 1024 * 1024  # a long sync with routes runs to tens of megabytes


def _key_matches(request: Request, key: str) -> bool:
    given = request.headers.get("authorization", "")
    if not given.startswith("Bearer "):
        return False
    return hmac.compare_digest(given[7:].strip().encode(), key.encode())


@router.post("/health")
async def receive(request: Request) -> dict[str, Any]:
    s = runs.settings(request.app.state.config)
    if not s["enabled"]:
        raise HTTPException(503, "Runs are not set up (RUNS_KEY).")
    if not _key_matches(request, s["key"]):
        raise HTTPException(401, "Wrong or missing runs key.")
    if int(request.headers.get("content-length") or 0) > MAX_BODY:
        raise HTTPException(413, "Too large: turn on Batch Requests in the automation.")
    try:
        body = json.loads(await request.body())
    except ValueError:
        raise HTTPException(400, "Not JSON: choose JSON, version 2, in the automation.") from None
    counts = runs.receive(request.app.state.store, body)
    log.info("runs: kept %d, skipped %d other workouts, %d unreadable",
             counts["kept"], counts["skipped"], counts["failed"])
    return counts


@router.get("")
def latest(request: Request) -> dict[str, Any]:
    return {"runs": runs.latest(request.app.state.store)}


@router.get("/overview")
def overview(request: Request) -> dict[str, Any]:
    """Runs and plan together for the Running page and the Home card (plan.md M28)."""
    zone = ZoneInfo(request.app.state.config.get("timezone", "Europe/Amsterdam"))
    return running.overview(request.app.state.store, zone, datetime.now(UTC))


@router.get("/plan")
def training_plan(request: Request) -> Any:
    """Runna's plan: the next sessions, this week's planned distance and the race."""
    payload = request.app.state.store.get_cache(runna.CACHE_KEY)
    if payload is None:
        raise HTTPException(503, "Runna's plan is not read yet (RUNNA_ICS_URL).")
    return payload


@router.get("/{run_id}")
def one(run_id: str, request: Request) -> dict[str, Any]:
    run = runs.one(request.app.state.store, run_id)
    if run is None:
        raise HTTPException(404, "No such run.")
    return run
