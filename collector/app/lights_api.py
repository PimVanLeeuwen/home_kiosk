"""The Lights page's side of the hub (M17): read the living room's lights and
change them. Changes are writes to the house, so they go through the same
same-origin check as every other write; the bridge's answer is what comes back.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field, model_validator

from .security import same_origin_json
from .sources import hue

router = APIRouter(prefix="/api/lights")
write = [Depends(same_origin_json)]


class Change(BaseModel):
    on: bool | None = None
    brightness: Annotated[int | None, Field(ge=1, le=100)] = None
    kelvin: int | None = None

    @model_validator(mode="after")
    def _something(self) -> Change:
        if self.on is None and self.brightness is None and self.kelvin is None:
            raise ValueError("nothing to change")
        if self.kelvin is not None and self.kelvin not in hue.KELVINS:
            raise ValueError(f"kelvin must be one of {', '.join(map(str, hue.KELVINS))}")
        return self


class RoomSwitch(BaseModel):
    on: bool


def _cfg(request: Request) -> dict[str, Any]:
    cfg = request.app.state.config
    if not hue.settings(cfg)["enabled"]:
        raise HTTPException(503, "The Hue Bridge is not set up (HUE_APPLICATION_KEY).")
    return cfg


def _bridge(request: Request) -> hue.Bridge | None:
    """Tests put a fake bridge here; normally a real one is made per call."""
    return getattr(request.app.state, "hue_bridge", None)


@router.get("")
def lights(request: Request) -> Any:
    payload = request.app.state.store.get_cache(hue.CACHE_KEY)
    if payload is None:
        raise HTTPException(503, "The lights are not read yet.")
    return payload


@router.put("/{group_id}", dependencies=write)
async def change(group_id: str, body: Change, request: Request) -> Any:
    cfg = _cfg(request)
    try:
        result = await hue.change(cfg, request.app.state.store, group_id, on=body.on,
                                  brightness=body.brightness, kelvin=body.kelvin,
                                  bridge=_bridge(request))
    except KeyError:
        raise HTTPException(404, "No such group of lights.") from None
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from None
    except Exception as exc:
        raise HTTPException(502, hue.reason(exc)) from None
    return result.model_dump(mode="json")


@router.post("/room", dependencies=write)
async def switch_room(body: RoomSwitch, request: Request) -> Any:
    cfg = _cfg(request)
    try:
        result = await hue.switch_room(cfg, request.app.state.store, body.on,
                                       bridge=_bridge(request))
    except Exception as exc:
        raise HTTPException(502, hue.reason(exc)) from None
    return result.model_dump(mode="json")
