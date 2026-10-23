"""The desk panels' side of the hub (plan.md M16). A board asks
/api/desk/board/<its MAC> for what to show (app/desk_boards.py says which panel
it is); /api/desk/<name> answers for a panel by name. app/desk.py builds both.

The board route records the visit on a GET: the boards are not browsers and
send no Origin, so `same_origin_json` cannot guard it. At worst a page could
add a made-up board to the list in Settings, where it can be forgotten. The
panels' own writes (/api/desk/save) need the board's device key instead.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Annotated, Any, Literal
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from . import desk, desk_alerts, desk_boards, desk_headlines, desk_home, desk_keys, desk_media
from .lights_api import Change, RoomSwitch
from .sources import hue, music, readeck, spotify

router = APIRouter(prefix="/api/desk")
ARTICLE = re.compile(r"^[0-9a-f]{16}$")

# The three panels, and "test" for a board on the bench (it shows the Now panel's screens).
PanelName = Literal["now", "home", "house", "test"]


async def _music(request: Request) -> dict[str, Any] | None:
    """The hub's Spotify state for the Home panel, the last good one (stale) while
    Spotify fails; None when there is none (the panel then shows its other screens)."""
    cfg = request.app.state.config
    if not spotify.settings(cfg)["enabled"]:
        return None
    try:
        return await music.latest(cfg, request.app.state.store)
    except Exception:
        return None


@router.get("/board/{mac}")
async def board(mac: str, request: Request,
                firmware: Annotated[str, Query(max_length=40)] = "",
                room: Annotated[int, Query(ge=1024, le=1 << 20)] = desk.ROOM) -> dict[str, Any]:
    """A board's screens; `room`: how much of an answer it can read (the hub leaves
    screens out to fit, desk.fit)."""
    mac = mac.lower()
    if not desk_boards.MAC.match(mac):
        raise HTTPException(422, "A board is asked for by its MAC address, like e8:f6:0a:e4:42:b0.")
    store = request.app.state.store
    visit = desk_boards.check_in(store, mac, firmware, key=desk_keys.presented(request))
    playing = await _music(request) if visit.panel == "home" else None
    answer = desk.answer(request.app.state.config, store, visit.panel, board=mac, music=playing)
    if visit.update:
        answer["update"] = True  # install the hub's firmware now (Settings, Update now)
    if visit.key:
        answer["key"] = visit.key  # its device key, until the board sends it back
    return desk.fit(answer, room)


class Dismiss(BaseModel):
    key: Annotated[str, Field(min_length=1, max_length=200)]


@router.post("/alerts/dismiss")
def alerts_dismiss(body: Dismiss, request: Request,
                   board: Annotated[str, Depends(desk_keys.board_key)]) -> dict[str, bool]:
    """Dismisses an error's takeover on all three panels until it resolves."""
    if not desk_alerts.dismiss(request.app.state.store, body.key, datetime.now(UTC)):
        raise HTTPException(404, "That alert is no longer open.")
    return {"ok": True}


class Save(BaseModel):
    article_id: str


@router.post("/save")
async def save(body: Save, request: Request,
               board: Annotated[str, Depends(desk_keys.board_key)]) -> Any:
    """A tap on a headline: saves the story to Readeck. Needs the board's key."""
    if not ARTICLE.match(body.article_id):
        raise HTTPException(404, "That story is no longer among the headlines.")
    try:
        found = await desk_headlines.save(request.app.state.config, request.app.state.store,
                                          body.article_id, board)
    except readeck.SaveError as exc:
        return JSONResponse(status_code=502, content={"detail": str(exc)})
    if not found:
        raise HTTPException(404, "That story is no longer among the headlines.")
    return {"saved": True}


@router.get("/picture/{article_id}/{size}")
def picture(article_id: str, size: Literal["lead", "thumb"], request: Request) -> Response:
    """A headline's stored picture as a small JPEG for the panels; nothing else."""
    if not ARTICLE.match(article_id):
        raise HTTPException(404, "No such picture.")
    data = desk_headlines.picture(request.app.state.store, article_id, size)
    if data is None:
        raise HTTPException(404, "No such picture.")
    return Response(data, media_type="image/jpeg",
                    headers={"Cache-Control": "public, max-age=86400"})


async def _lights(request: Request, change) -> Any:
    """Runs a change on the living room's lights; answers with the panel's lights screen."""
    cfg = request.app.state.config
    if not hue.settings(cfg)["enabled"]:
        raise HTTPException(503, "The Hue Bridge is not set up.")
    try:
        await change(cfg, getattr(request.app.state, "hue_bridge", None))
    except KeyError:
        raise HTTPException(404, "No such group of lights.") from None
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from None
    except Exception as exc:
        raise HTTPException(502, hue.reason(exc)) from None
    zone = ZoneInfo(cfg.get("timezone", "UTC"))
    return desk_home.lights_screen(request.app.state.store, zone, datetime.now(UTC))


@router.post("/lights/room")
async def lights_room(body: RoomSwitch, request: Request,
                      board: Annotated[str, Depends(desk_keys.board_key)]) -> Any:
    """All the living room's lights on or off, from a panel."""
    store = request.app.state.store
    return await _lights(request, lambda cfg, bridge: hue.switch_room(cfg, store, body.on,
                                                                       bridge=bridge))


@router.post("/lights/{group_id}")
async def lights_group(group_id: str, body: Change, request: Request,
                       board: Annotated[str, Depends(desk_keys.board_key)]) -> Any:
    """Switch, dim or set the white of one group, from a panel."""
    store = request.app.state.store
    return await _lights(request, lambda cfg, bridge: hue.change(
        cfg, store, group_id, on=body.on, brightness=body.brightness, kelvin=body.kelvin,
        bridge=bridge))


@router.get("/poster/{source}/{item_id}")
async def poster(source: Literal["sonarr", "radarr"], item_id: int, request: Request) -> Response:
    """A download's poster from the current Media answer, as a small JPEG for House."""
    try:
        data = await desk_media.poster(request.app.state.config, request.app.state.store,
                                       source, item_id)
    except LookupError:
        raise HTTPException(404, "No such poster.") from None
    except Exception:
        raise HTTPException(502, "The poster could not be loaded.") from None
    return Response(data, media_type="image/jpeg",
                    headers={"Cache-Control": "public, max-age=86400"})


@router.get("/cover/{key}/{size}")
async def cover(key: str, size: Literal["big", "tile", "thumb"], request: Request) -> Response:
    """A Spotify cover the hub stored, as a small JPEG for the Home panel."""
    if not desk_home.COVER_KEY.match(key):
        raise HTTPException(404, "No such cover.")
    try:
        data = await desk_home.cover(request.app.state.store, key, size)
    except Exception:
        raise HTTPException(502, "The cover could not be loaded.") from None
    if data is None:
        raise HTTPException(404, "No such cover.")
    return Response(data, media_type="image/jpeg",
                    headers={"Cache-Control": "public, max-age=86400"})


async def _spotify(request: Request, act) -> dict[str, bool]:
    cfg = request.app.state.config
    if not spotify.settings(cfg)["enabled"]:
        raise HTTPException(503, "Spotify is not set up.")
    try:
        await act(cfg, request.app.state.store)
    except spotify.SpotifyError as exc:
        raise HTTPException(exc.status, str(exc)) from None
    except Exception:
        raise HTTPException(502, "Spotify could not be reached.") from None
    return {"ok": True}


@router.post("/music/favourite/{position}")
async def music_favourite(position: Annotated[int, Path(ge=0, le=spotify.FAVOURITES)],
                          request: Request,
                          board: Annotated[str, Depends(desk_keys.board_key)]) -> Any:
    """Starts a favourite from the Home panel (on the device that plays, else the
    living room's Apple TV, woken when needed)."""
    return await _spotify(request, lambda cfg, store: music.play_favourite(cfg, store, position))


@router.post("/music/{action}")
async def music_control(action: Literal["play", "pause", "next", "previous"], request: Request,
                        board: Annotated[str, Depends(desk_keys.board_key)]) -> Any:
    """Play, pause or skip from the Home panel."""
    return await _spotify(request, lambda cfg, store: music.control(cfg, store, action))


@router.get("/{name}")
async def panel(name: PanelName, request: Request) -> dict[str, Any]:
    playing = await _music(request) if name == "home" else None
    return desk.answer(request.app.state.config, request.app.state.store, name, music=playing)
