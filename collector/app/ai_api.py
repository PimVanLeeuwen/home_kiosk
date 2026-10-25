"""Settings, AI (plan.md M26): this month's spend against the cap, and a switch
per feature. Turning a feature on is a change, so it goes through the same-origin
check; the key itself never leaves the NAS's .env.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request

from . import ai, briefing
from .security import same_origin_json

router = APIRouter(prefix="/api/ai")
write = [Depends(same_origin_json)]


def status(request: Request) -> dict[str, Any]:
    cfg, store = request.app.state.config, request.app.state.store
    now = datetime.now(UTC)
    s = ai.settings(cfg)
    spent, calls = ai.month_spend(store, cfg, now)
    return {
        "as_of": now.isoformat(), "stale": False,
        "configured": s["enabled"], "cap": s["cap_eur"],
        "spent": round(spent, 4), "calls": calls,
        "capped": spent >= s["cap_eur"],
        "features": [{"id": f, "label": label, "on": on}
                     for (f, label), on in zip(ai.FEATURES.items(),
                                               ai.switches(store).values(), strict=True)],
    }


@router.get("")
def get_status(request: Request) -> dict[str, Any]:
    return status(request)


@router.put("/features", dependencies=write)
def put_features(changes: dict[str, bool], request: Request) -> dict[str, Any]:
    try:
        ai.set_switches(request.app.state.store, changes)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from None
    return status(request)


@router.post("/briefing/now", dependencies=write)
async def briefing_now(request: Request) -> dict[str, Any]:
    """Write and send today's morning digest now: to try it, or after a failed morning."""
    made = await briefing.run(request.app.state.config, request.app.state.store)
    if made is None:
        raise HTTPException(409, "No digest: AI is off, the morning digest is switched off, "
                                 "the cap is reached, or Claude did not answer.")
    return made.model_dump(mode="json")
