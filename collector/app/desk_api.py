"""The desk panels' side of the hub (plan.md M16). A panel only knows its
name and asks /api/desk/<name> for what to show; app/desk.py builds it.
"""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Request

from . import desk

router = APIRouter(prefix="/api/desk")

# The three panels, and "test" for a board on the bench (it shows the Now panel's screens).
PanelName = Literal["now", "home", "house", "test"]


@router.get("/{name}")
def panel(name: PanelName, request: Request) -> dict[str, Any]:
    return desk.answer(request.app.state.config, request.app.state.store, name)
