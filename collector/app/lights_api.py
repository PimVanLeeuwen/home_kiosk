"""The Lights page's side of the hub (M17): read the living room's lights and
change them. Changes are writes to the house, so they go through the same
same-origin check as every other write; the bridge's answer is what comes back.
"""

from __future__ import annotations

from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field, StringConstraints, model_validator

from .alerts import core as settings_store
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


# --- the floor plan (plan.md M27, O) --------------------------------------------------

PLAN_SETTING = "lights_plan"
Share = Annotated[float, Field(ge=0, le=1)]  # a place on the plan, 0 to 1 of its width or depth
LightId = Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9-]{1,64}$")]


class Spot(BaseModel):
    x: Share
    y: Share


class Piece(BaseModel):
    kind: Literal["sofa", "table", "kitchen", "tv"]
    x: Share  # its centre
    y: Share
    w: Annotated[float, Field(gt=0, le=1)]
    h: Annotated[float, Field(gt=0, le=1)]


class Plan(BaseModel):
    """The living room from above: its width over its depth, where each light hangs, and a
    few furniture outlines, all placed once in Settings."""
    aspect: Annotated[float, Field(ge=1, le=3)] = 1.7
    lights: Annotated[dict[LightId, Spot], Field(max_length=32)] = {}
    furniture: Annotated[list[Piece], Field(max_length=8)] = []


DEFAULT_PLAN = Plan(furniture=[
    Piece(kind="kitchen", x=0.3, y=0.52, w=0.48, h=0.13),
    Piece(kind="table", x=0.84, y=0.28, w=0.18, h=0.19),
    Piece(kind="sofa", x=0.78, y=0.7, w=0.26, h=0.2),
    Piece(kind="tv", x=0.78, y=0.94, w=0.2, h=0.04),
])


@router.get("/plan")
def plan(request: Request) -> Plan:
    """Where the lights are, for the Lights page's floor plan; a sensible start until placed."""
    stored = settings_store.get_setting(request.app.state.store, PLAN_SETTING, None)
    return Plan.model_validate(stored) if stored else DEFAULT_PLAN


@router.put("/plan", dependencies=write)
def put_plan(body: Plan, request: Request) -> Plan:
    settings_store.put_setting(request.app.state.store, PLAN_SETTING, body.model_dump())
    return body


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
