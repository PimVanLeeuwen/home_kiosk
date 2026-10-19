"""The desk panels' side of the hub (plan.md M16). A board asks
/api/desk/board/<its MAC> for what to show (app/desk_boards.py says which panel
it is); /api/desk/<name> answers for a panel by name. app/desk.py builds both.

The board route records the visit on a GET: the boards are not browsers and
send no Origin, so `same_origin_json` cannot guard it. At worst a page could
add a made-up board to the list in Settings, where it can be forgotten.
"""

from __future__ import annotations

from typing import Annotated, Any, Literal

from fastapi import APIRouter, HTTPException, Query, Request

from . import desk, desk_boards

router = APIRouter(prefix="/api/desk")

# The three panels, and "test" for a board on the bench (it shows the Now panel's screens).
PanelName = Literal["now", "home", "house", "test"]


@router.get("/board/{mac}")
def board(mac: str, request: Request,
          firmware: Annotated[str, Query(max_length=40)] = "") -> dict[str, Any]:
    mac = mac.lower()
    if not desk_boards.MAC.match(mac):
        raise HTTPException(422, "A board is asked for by its MAC address, like e8:f6:0a:e4:42:b0.")
    store = request.app.state.store
    panel = desk_boards.check_in(store, mac, firmware)
    return desk.answer(request.app.state.config, store, panel, board=mac)


@router.get("/{name}")
def panel(name: PanelName, request: Request) -> dict[str, Any]:
    return desk.answer(request.app.state.config, request.app.state.store, name)
