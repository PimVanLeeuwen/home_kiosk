"""The Ask page's side of the hub (plan.md M35): a question, and a confirmed change.

Both are same-origin JSON like every other write: the question costs money, the change
changes the house. The Shortcut "Ask the hub" posts without an Origin, which passes.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from . import ask
from .security import same_origin_json

router = APIRouter(prefix="/api/ask")
write = [Depends(same_origin_json)]


def _servers(request: Request) -> tuple[Any, Any]:
    """The MCP servers main.py made: the house tools, and the same with the write tools."""
    return request.app.state.mcp_read, request.app.state.mcp_write


@router.post("", dependencies=write)
async def question(body: ask.Question, request: Request) -> ask.Answer:
    read, writes = _servers(request)
    try:
        return await ask.answer(request.app.state.config, request.app.state.store, body,
                                read, writes, client=getattr(request.app.state, "ask_client",
                                                             None))
    except ask.AskError as exc:
        raise HTTPException(exc.status, str(exc)) from None


class Change(BaseModel):
    tool: Annotated[str, Field(max_length=40)]
    args: dict[str, Any] = {}


@router.post("/confirm", dependencies=write)
async def confirm(body: Change, request: Request) -> dict[str, Any]:
    _, writes = _servers(request)
    try:
        return await ask.confirm(writes, body.tool, body.args)
    except ask.AskError as exc:
        raise HTTPException(exc.status, str(exc)) from None
