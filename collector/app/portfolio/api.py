"""Endpoints for the Portfolio page. The summary stays at /api/portfolio (main.py)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from ..security import same_origin_json
from ..sources.ghostfolio import CHARTS_KEY, GhostfolioError
from . import degiro, degiro_import, holding
from .models import HoldingDetail

router = APIRouter(prefix="/api")
RANGES = ("month", "ytd", "year", "max")


def _cached(request: Request, key: str) -> dict[str, Any]:
    payload = request.app.state.store.get_cache(key)
    if payload is None:
        raise HTTPException(503, f"no {key} data collected yet")
    return payload


@router.get("/portfolio/history")
def history(request: Request, range: str = "year") -> dict[str, Any]:
    """Value (and the amount invested) over one range, for the page's chart."""
    if range not in RANGES:
        raise HTTPException(422, f"range must be one of {', '.join(RANGES)}")
    charts = _cached(request, CHARTS_KEY)
    return {"as_of": charts["as_of"], "stale": charts.get("stale", False), "range": range,
            "points": charts["ranges"].get(range, [])}


@router.get("/portfolio/holdings/{data_source}/{symbol}")
async def holding_detail(data_source: str, symbol: str, request: Request) -> HoldingDetail:
    try:
        return await holding.detail(
            request.app.state.config, data_source, symbol,
            getattr(request.app.state, "ghostfolio_transport", None))
    except holding.NotFound as exc:
        raise HTTPException(404, "No such holding.") from exc
    except Exception as exc:  # GhostfolioError or transport trouble
        raise HTTPException(502, "Ghostfolio is not answering.") from exc


@router.get("/indices")
def indices(request: Request) -> dict[str, Any]:
    return _cached(request, "indices")


# --- DEGIRO import ---------------------------------------------------------------------------

write = [Depends(same_origin_json)]
Csv = Annotated[str, Field(min_length=1, max_length=degiro.MAX_BYTES)]


class PreviewRequest(BaseModel):
    csv: Csv
    choices: dict[str, degiro_import.Choice] = {}


class ImportRequest(PreviewRequest):
    account_id: Annotated[str, Field(min_length=1, max_length=100)]


def _failed(exc: Exception) -> HTTPException:
    if isinstance(exc, (degiro.ExportError, degiro_import.DegiroError)):
        return HTTPException(422, str(exc))
    if isinstance(exc, GhostfolioError) and exc.detail:
        return HTTPException(502, f"Ghostfolio refused: {exc.detail}")
    return HTTPException(502, "Ghostfolio is not answering.")


@router.post("/portfolio/degiro/preview", dependencies=write)
async def degiro_preview(body: PreviewRequest, request: Request) -> degiro_import.Preview:
    """What an import would do. Writes nothing."""
    try:
        degiro_import.check_choices(body.choices)
        return await degiro_import.preview(
            request.app.state.config, request.app.state.store, body.csv, body.choices,
            getattr(request.app.state, "ghostfolio_transport", None))
    except Exception as exc:
        raise _failed(exc) from exc


@router.post("/portfolio/degiro/import", dependencies=write)
async def degiro_run(body: ImportRequest, request: Request) -> dict[str, int]:
    """Import the new trades into Ghostfolio, then refresh the portfolio."""
    try:
        result = await degiro_import.run_import(
            request.app.state.config, request.app.state.store, body.csv, body.account_id,
            body.choices, getattr(request.app.state, "ghostfolio_transport", None))
    except Exception as exc:
        raise _failed(exc) from exc
    scheduler = getattr(request.app.state, "scheduler", None)
    if scheduler and scheduler.get_job("portfolio"):
        scheduler.get_job("portfolio").modify(next_run_time=datetime.now(UTC))
    return result


@router.get("/portfolio/degiro/choices")
def degiro_choices(request: Request) -> dict[str, degiro_import.Choice]:
    """The symbols (or leave-outs) remembered per ISIN."""
    return degiro_import.saved_choices(request.app.state.store)


@router.delete("/portfolio/degiro/choices/{isin}", dependencies=write)
def forget_degiro_choice(isin: str, request: Request) -> dict[str, degiro_import.Choice]:
    """Forget one; the next upload asks about that product again."""
    if not degiro_import.forget_choice(request.app.state.store, isin):
        raise HTTPException(404, "Nothing remembered for that ISIN.")
    return degiro_import.saved_choices(request.app.state.store)
