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

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response
from pydantic import BaseModel, Field

from . import paint_streets, running
from .security import same_origin_json
from .sources import runna, runs, streets

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


@router.get("/streets")
def streets_status(request: Request) -> dict[str, Any]:
    """The areas run in, home first, and whether each one's streets are in (Settings, Running)."""
    return streets.status(request.app.state.store)


class StreetsAsk(BaseModel):
    area: str = Field(max_length=40)


@router.post("/streets", dependencies=[Depends(same_origin_json)])
async def fetch_streets(request: Request, ask: StreetsAsk) -> dict[str, Any]:
    """Asks Overpass once for the streets of one area run in (plan.md M28, step 5)."""
    store = request.app.state.store
    try:
        return await streets.fetch(store, ask.area)
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from None
    except Exception as exc:
        log.warning("streets: Overpass failed: %s", type(exc).__name__)
        raise HTTPException(
            502, "OpenStreetMap's Overpass could not be reached; try again later.") from None


_picture: dict[str, Any] = {"key": None, "jpeg": None}


@router.get("/streets/picture")
def streets_picture(request: Request) -> Response:
    """Your streets for the Running page: this year's runs over the town, painted once per
    change."""
    store = request.app.state.store
    zone = ZoneInfo(request.app.state.config.get("timezone", "Europe/Amsterdam"))
    local = datetime.now(zone)
    since = datetime(local.year, 1, 1, tzinfo=zone).astimezone(UTC).isoformat()
    home = streets.at_home(store, since)
    year = home["runs"]
    if not year:
        raise HTTPException(404, "No runs this year yet.")
    key = (since, len(year), year[-1]["id"], (home["streets"] or {}).get("fetched_at"))
    if _picture["key"] != key:
        _picture.update(key=key, jpeg=paint_streets.web_jpeg(store, since))
    return Response(_picture["jpeg"], media_type="image/jpeg",
                    headers={"Cache-Control": "private, max-age=300"})


@router.get("/plan")
def training_plan(request: Request) -> Any:
    """Runna's plan: the next sessions, this week's planned distance and the race."""
    payload = request.app.state.store.get_cache(runna.CACHE_KEY)
    if payload is None:
        raise HTTPException(503, "Runna's plan is not read yet (RUNNA_ICS_URL).")
    return payload


_route_streets: dict[str, Any] = {"key": None, "webp": None}


@router.get("/{run_id}/streets")
def run_streets(run_id: str, request: Request) -> Response:
    """The streets under a run's route on the Running page (its own area's, once fetched)."""
    store = request.app.state.store
    run = runs.one(store, run_id, running.LAST_POINTS)
    route = run["route"] if run else []
    kept = streets.kept_for(store, streets.middle(route)) if route else None
    if kept is None:
        raise HTTPException(404, "No streets fetched for this run's area.")
    key = (run_id, kept["fetched_at"])
    if _route_streets["key"] != key:
        _route_streets.update(key=key, webp=paint_streets.route_streets(route, kept["shapes"]))
    return Response(_route_streets["webp"], media_type="image/webp",
                    headers={"Cache-Control": "private, max-age=86400"})


@router.get("/{run_id}")
def one(run_id: str, request: Request) -> dict[str, Any]:
    run = runs.one(request.app.state.store, run_id)
    if run is None:
        raise HTTPException(404, "No such run.")
    return run
