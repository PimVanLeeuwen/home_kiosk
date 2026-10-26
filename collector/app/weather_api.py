"""The weather for the hub's pages (plan.md M27, Q): now from Buienradar, the week from
Open-Meteo and, while rain is coming, the radar round home. Only cached answers: nothing is
fetched here."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, Response

from . import paint_radar
from .sources import forecast, radar, weather

router = APIRouter()


def _serve(request: Request, key: str) -> Any:
    payload = request.app.state.store.get_cache(key)
    if payload is None:
        return JSONResponse(status_code=503, content={"detail": f"no {key} data collected yet"})
    return payload


@router.get("/api/weather")
def weather_now(request: Request) -> Any:
    return _serve(request, weather.CACHE_KEY)


@router.get("/api/forecast")
def weather_forecast(request: Request) -> Any:
    """The week by the hour from Open-Meteo, for the Weather page (plan.md M27, Q)."""
    return _serve(request, forecast.CACHE_KEY)


@router.get("/api/radar")
def rain_radar(request: Request) -> Any:
    """Whether rain is coming within two hours, and the radar frame's time (sources/radar.py)."""
    return _serve(request, radar.CACHE_KEY)


@router.get("/api/radar/map")
def rain_radar_map(request: Request) -> Response:
    """The radar round home in the hub's colours; only while rain is coming."""
    cached = request.app.state.store.get_cache(radar.CACHE_KEY) or {}
    home = cached.get("home") or [250, 256]
    picture = paint_radar.web_picture(home, cached.get("stamp")) if cached.get("wet") else None
    if not picture:
        return JSONResponse(status_code=404, content={"detail": "No rain on the way."})
    return Response(picture, media_type="image/jpeg",
                    headers={"Cache-Control": "private, max-age=300"})
