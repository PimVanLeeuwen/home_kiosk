"""The Reminders page's side of the hub (plan.md M32): list, add, change, tick off and delete
reminders. Every change goes through the same-origin check; the panels only read them.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from . import reminders
from .security import same_origin_json

router = APIRouter(prefix="/api/reminders")
write = [Depends(same_origin_json)]
MAX_REMINDERS = 500


def _zone(request: Request) -> ZoneInfo:
    return ZoneInfo(request.app.state.config.get("timezone", "UTC"))


def _overview(request: Request) -> dict[str, Any]:
    return reminders.overview(request.app.state.store, datetime.now(UTC), _zone(request))


@router.get("")
def overview(request: Request) -> dict[str, Any]:
    return _overview(request)


@router.post("", dependencies=write)
def add(draft: reminders.Draft, request: Request) -> dict[str, Any]:
    store = request.app.state.store
    if len(reminders.all_reminders(store)) >= MAX_REMINDERS:
        raise HTTPException(422, f"At most {MAX_REMINDERS} reminders.")
    reminders.add(store, draft)
    return _overview(request)


@router.put("/{reminder_id}", dependencies=write)
def change(reminder_id: int, draft: reminders.Draft, request: Request) -> dict[str, Any]:
    if not reminders.change(request.app.state.store, reminder_id, draft):
        raise HTTPException(404, "No such reminder.")
    return _overview(request)


@router.delete("/{reminder_id}", dependencies=write)
def delete(reminder_id: int, request: Request) -> dict[str, Any]:
    if not reminders.delete(request.app.state.store, reminder_id):
        raise HTTPException(404, "No such reminder.")
    return _overview(request)


class Done(BaseModel):
    day: date
    done: bool = True


@router.post("/{reminder_id}/done", dependencies=write)
def done(reminder_id: int, body: Done, request: Request) -> dict[str, Any]:
    """Ticks off (or back on) one day's occurrence, never the series."""
    store = request.app.state.store
    found = reminders.get(store, reminder_id)
    if found is None:
        raise HTTPException(404, "No such reminder.")
    if not reminders.occurs(found, body.day):
        raise HTTPException(422, "That reminder does not fall on that day.")
    reminders.set_done(store, reminder_id, body.day, body.done)
    return _overview(request)
