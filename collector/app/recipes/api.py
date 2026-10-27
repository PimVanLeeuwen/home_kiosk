"""Endpoints for Recipes (plan.md M30). Recipes change only by pasting JSON: a paste is checked
first (`/check`: its faults, or what it would change), then saved all or nothing (`/import`).
"""

from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Body, Depends, HTTPException, Request
from pydantic import BaseModel, ValidationError

from ..security import same_origin_json
from . import schema, store
from .changes import changes

router = APIRouter(prefix="/api/recipes")
write = [Depends(same_origin_json)]

MAX_BODY = 8 * 1024 * 1024  # Copy all of a few hundred recipes pasted back, with room to spare
MAX_RECIPES = 1000


def _small_enough(request: Request) -> None:
    if int(request.headers.get("content-length") or 0) > MAX_BODY:
        raise HTTPException(413, "Too large to paste at once.")


class Paste(BaseModel):
    data: Any
    replace: bool = False


def _items(data: Any) -> tuple[list[Any], bool]:
    """The recipes in a paste: one, a list, or Copy all's export. True when it was one."""
    if isinstance(data, dict) and isinstance(data.get("recipes"), list):
        return data["recipes"], False
    if isinstance(data, dict):
        return [data], True
    if isinstance(data, list):
        return data, False
    return [], False


def _parse(data: Any) -> tuple[list[schema.Recipe], list[dict[str, str]]]:
    items, single = _items(data)
    if not items:
        return [], [{"path": "(the paste)",
                     "message": "should be one recipe, a list of recipes, or Copy all's JSON"}]
    if len(items) > MAX_RECIPES:
        return [], [{"path": "(the paste)", "message": f"has more than {MAX_RECIPES} recipes"}]
    recipes, problems = [], []
    for i, item in enumerate(items):
        try:
            recipes.append(schema.parse(item))
        except ValidationError as exc:
            problems += schema.problems(exc, "" if single else f"[{i}]")
    seen = Counter(r.id for r in recipes)
    problems += [{"path": "id", "message": f'"{rid}" is in the paste {n} times'}
                 for rid, n in seen.items() if n > 1]
    return recipes, problems


def _unprocessable(problems: list[dict[str, str]]) -> HTTPException:
    return HTTPException(422, {"problems": problems})


@router.get("")
def recipes(request: Request) -> dict[str, Any]:
    rows = store.summaries(request.app.state.store)
    tags = Counter(tag for row in rows for tag in row["tags"])
    return {"as_of": datetime.now(UTC).isoformat(), "stale": False, "count": len(rows),
            "review_count": sum(row["needs_review"] for row in rows),
            "tags": [{"tag": t, "count": n} for t, n in
                     sorted(tags.items(), key=lambda kv: (-kv[1], kv[0]))],
            "recipes": rows}


@router.get("/schema")
def recipe_schema() -> dict[str, Any]:
    return {"schema": schema.SCHEMA_ID, "guide": schema.GUIDE, "json_schema": schema.json_schema()}


@router.get("/export")
def export(request: Request) -> dict[str, Any]:
    """Copy all: the guide, the schema and every recipe, to paste into a Claude chat."""
    return {**recipe_schema(),
            "recipes": list(store.bodies(request.app.state.store).values())}


@router.post("/check", dependencies=[*write, Depends(_small_enough)])
def check(request: Request, paste: Paste) -> dict[str, Any]:
    """What a paste would do, without saving: its faults, or per recipe new, same or changes."""
    recipes, problems = _parse(paste.data)
    if problems:
        return {"ok": False, "problems": problems, "recipes": []}
    old = store.bodies(request.app.state.store, [r.id for r in recipes])
    out = []
    for recipe in recipes:
        body = recipe.dump()
        was = old.get(recipe.id)
        if was is None:
            out.append({"id": recipe.id, "title": recipe.title, "result": "new", "changes": []})
        else:
            lines = changes(was, body)
            out.append({"id": recipe.id, "title": recipe.title,
                        "result": "replace" if lines or was != body else "same",
                        "changes": lines})
    return {"ok": True, "problems": [], "recipes": out}


@router.post("/import", dependencies=[*write, Depends(_small_enough)])
def import_recipes(request: Request, paste: Paste) -> dict[str, Any]:
    """Saves a paste all or nothing. Replacing needs `replace`, after the check was shown."""
    recipes, problems = _parse(paste.data)
    if problems:
        raise _unprocessable(problems)
    db = request.app.state.store
    old = store.bodies(db, [r.id for r in recipes])
    replacing = [r.id for r in recipes if r.id in old and old[r.id] != r.dump()]
    if replacing and not paste.replace:
        raise HTTPException(409, {"message": "This would replace recipes.", "ids": replacing})
    saved = [{"id": r.id, "title": r.title, "result": store.save(db, r)} for r in recipes]
    return {"saved": saved}


@router.get("/{recipe_id}")
def recipe(request: Request, recipe_id: str) -> dict[str, Any]:
    found = store.get(request.app.state.store, recipe_id)
    if found is None:
        raise HTTPException(404, "No such recipe.")
    return found


@router.put("/{recipe_id}", dependencies=[*write, Depends(_small_enough)])
def replace(request: Request, recipe_id: str, data: Annotated[Any, Body()]) -> dict[str, Any]:
    """Paste JSON on a recipe: replaces this one only, so its id has to match."""
    try:
        parsed = schema.parse(data)
    except ValidationError as exc:
        raise _unprocessable(schema.problems(exc)) from None
    if parsed.id != recipe_id:
        raise _unprocessable([{"path": "id", "message":
                               f'is "{parsed.id}"; this recipe is "{recipe_id}"'}])
    result = store.save(request.app.state.store, parsed)
    return {"result": result, **(store.get(request.app.state.store, recipe_id) or {})}


@router.post("/{recipe_id}/undo", dependencies=write)
def undo(request: Request, recipe_id: str) -> dict[str, Any]:
    db = request.app.state.store
    if store.get(db, recipe_id) is None:
        raise HTTPException(404, "No such recipe.")
    if not store.undo(db, recipe_id):
        raise HTTPException(409, "Nothing to undo.")
    return store.get(db, recipe_id) or {}


@router.delete("/{recipe_id}", dependencies=write)
def delete(request: Request, recipe_id: str) -> dict[str, Any]:
    if not store.delete(request.app.state.store, recipe_id):
        raise HTTPException(404, "No such recipe.")
    return {"deleted": recipe_id}
