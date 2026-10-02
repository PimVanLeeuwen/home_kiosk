"""Endpoints for the Portfolio page. The summary stays at /api/portfolio (main.py)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request

from ..sources.ghostfolio import CHARTS_KEY
from . import holding
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
