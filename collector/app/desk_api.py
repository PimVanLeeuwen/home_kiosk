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
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from . import desk, desk_boards, desk_headlines, desk_keys
from .sources import readeck

router = APIRouter(prefix="/api/desk")
ARTICLE = re.compile(r"^[0-9a-f]{16}$")

# The three panels, and "test" for a board on the bench (it shows the Now panel's screens).
PanelName = Literal["now", "home", "house", "test"]


@router.get("/board/{mac}")
def board(mac: str, request: Request,
          firmware: Annotated[str, Query(max_length=40)] = "") -> dict[str, Any]:
    mac = mac.lower()
    if not desk_boards.MAC.match(mac):
        raise HTTPException(422, "A board is asked for by its MAC address, like e8:f6:0a:e4:42:b0.")
    store = request.app.state.store
    visit = desk_boards.check_in(store, mac, firmware)
    answer = desk.answer(request.app.state.config, store, visit.panel, board=mac)
    if visit.update:
        answer["update"] = True  # install the hub's firmware now (Settings, Update now)
    if visit.key:
        answer["key"] = visit.key  # its device key, handed over this once
    return answer


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


@router.get("/{name}")
def panel(name: PanelName, request: Request) -> dict[str, Any]:
    return desk.answer(request.app.state.config, request.app.state.store, name)
