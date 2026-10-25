"""The Music page's side of the hub (M18): what plays, the controls, the
favourites, and connecting Spotify. Writes to Spotify are same-origin only.
"""

from __future__ import annotations

import logging
import time
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field

from .security import same_origin_json
from .sources import music, spotify

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/music")
write = [Depends(same_origin_json)]

def _cfg(request: Request) -> dict[str, Any]:
    cfg = request.app.state.config
    if not spotify.settings(cfg)["enabled"]:
        raise HTTPException(503, "Spotify is not set up (SPOTIFY_CLIENT_ID).")
    return cfg


def _failed(exc: Exception) -> HTTPException:
    if isinstance(exc, spotify.SpotifyError):
        return HTTPException(exc.status, str(exc))
    log.warning("spotify failed: %s", type(exc).__name__)
    return HTTPException(502, "Spotify could not be reached.")


@router.get("")
async def now(request: Request) -> Any:
    cfg = _cfg(request)
    try:
        return await music.latest(cfg, request.app.state.store)
    except Exception as exc:
        raise _failed(exc) from None


@router.get("/login")
def login(request: Request) -> RedirectResponse:
    """Starts connecting: the browser goes to Spotify and comes back to /callback."""
    cfg = _cfg(request)
    return RedirectResponse(spotify.login_url(cfg, request.app.state.store), status_code=302)


@router.get("/callback")
async def callback(request: Request, code: str = "", state: str = "",
                   error: str = "") -> RedirectResponse:
    cfg = _cfg(request)
    if error or not code:
        return RedirectResponse("/settings?music=cancelled#music", status_code=302)
    try:
        await spotify.CLIENT.finish_login(cfg, request.app.state.store, code, state)
    except Exception as exc:
        log.warning("spotify sign-in failed: %s", type(exc).__name__)
        return RedirectResponse("/settings?music=failed#music", status_code=302)
    return RedirectResponse("/settings?music=connected#music", status_code=302)


@router.post("/disconnect", dependencies=write)
def disconnect(request: Request) -> dict[str, bool]:
    spotify.disconnect(request.app.state.store)
    music.forget(request.app.state.store)
    return {"connected": False}


@router.post("/control/{action}", dependencies=write)
async def control(action: Literal["play", "pause", "next", "previous"],
                  request: Request) -> dict[str, bool]:
    try:
        await music.control(_cfg(request), request.app.state.store, action)
    except Exception as exc:
        raise _failed(exc) from None
    return {"ok": True}


class Volume(BaseModel):
    percent: Annotated[int, Field(ge=0, le=100)]


@router.put("/volume", dependencies=write)
async def volume(body: Volume, request: Request) -> dict[str, bool]:
    try:
        await music.volume(_cfg(request), request.app.state.store, body.percent)
    except Exception as exc:
        raise _failed(exc) from None
    return {"ok": True}


class Transfer(BaseModel):
    device_id: Annotated[str, Field(min_length=1, max_length=100)]


@router.post("/transfer", dependencies=write)
async def transfer(body: Transfer, request: Request) -> dict[str, bool]:
    try:
        await music.transfer(_cfg(request), request.app.state.store, body.device_id)
    except Exception as exc:
        raise _failed(exc) from None
    return {"ok": True}


@router.get("/playlists")
async def playlists(request: Request) -> Any:
    try:
        return await music.playlists(_cfg(request), request.app.state.store)
    except Exception as exc:
        raise _failed(exc) from None


class Favourites(BaseModel):
    ids: Annotated[list[Annotated[str, Field(min_length=1, max_length=64)]],
                   Field(max_length=spotify.FAVOURITES)]


@router.put("/favourites", dependencies=write)
async def set_favourites(body: Favourites, request: Request) -> Any:
    try:
        return await music.set_favourites(_cfg(request), request.app.state.store, body.ids)
    except Exception as exc:
        raise _failed(exc) from None


@router.post("/favourites/{position}/play", dependencies=write)
async def play_favourite(position: int, request: Request) -> dict[str, Any]:
    started = time.monotonic()
    try:
        device = await music.play_favourite(_cfg(request), request.app.state.store, position)
    except Exception as exc:
        raise _failed(exc) from None
    return {"ok": True, "device_id": device, "seconds": round(time.monotonic() - started, 1)}


@router.get("/covers/{key}")
async def cover(key: str, request: Request) -> Response:
    """Only covers seen in Spotify's answers, stored small; not an open proxy."""
    try:
        found = await spotify.cover(request.app.state.store, key, spotify.CLIENT.transport)
    except Exception:
        raise HTTPException(502, "The cover could not be loaded.") from None
    if found is None:
        raise HTTPException(404, "No such cover.")
    return Response(found[0], media_type="image/webp", headers={
        "Cache-Control": "private, max-age=86400", "X-Content-Type-Options": "nosniff"})
