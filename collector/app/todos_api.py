"""The Todos page's side of the hub (plan.md M37): list, add, change, tick off (remove) and
undo. Every change goes through the same-origin check; the panel only reads them.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request

from . import config, todos
from .security import same_origin_json

router = APIRouter(prefix="/api/todos")
write = [Depends(same_origin_json)]


def _overview(request: Request) -> dict[str, Any]:
    now = datetime.now(UTC)
    day = now.astimezone(config.zone(request.app.state.config)).date()
    return todos.overview(request.app.state.store, now, day)


def _room(store: Any) -> None:
    if todos.count(store) >= todos.MAX_OPEN:
        raise HTTPException(422, f"At most {todos.MAX_OPEN} open todos.")


@router.get("")
def overview(request: Request) -> dict[str, Any]:
    return _overview(request)


@router.post("", dependencies=write)
def add(draft: todos.Draft, request: Request) -> dict[str, Any]:
    store = request.app.state.store
    _room(store)
    todos.add(store, draft)
    return _overview(request)


@router.put("/{todo_id}", dependencies=write)
def change(todo_id: int, draft: todos.Draft, request: Request) -> dict[str, Any]:
    if not todos.change(request.app.state.store, todo_id, draft):
        raise HTTPException(404, "No such todo.")
    return _overview(request)


@router.delete("/{todo_id}", dependencies=write)
def remove(todo_id: int, request: Request) -> dict[str, Any]:
    """Ticks a todo off. The answer carries it as `removed`, for the page's Undo."""
    removed = todos.remove(request.app.state.store, todo_id)
    if removed is None:
        raise HTTPException(404, "No such todo.")
    return _overview(request) | {"removed": removed.model_dump(mode="json")}


@router.post("/restore", dependencies=write)
def restore(todo: todos.Todo, request: Request) -> dict[str, Any]:
    """Undo: puts back the todo a tick removed, with its id and age."""
    store = request.app.state.store
    _room(store)
    if not todos.restore(store, todo):
        raise HTTPException(409, "That todo is already there.")
    return _overview(request)
