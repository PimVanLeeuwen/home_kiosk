"""Endpoints for senders (/api/notify) and the Alerts page (/api/alerts/*)."""

from __future__ import annotations

import hmac
import re
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field, field_validator

from ..security import same_origin_json
from . import core, rules

router = APIRouter(prefix="/api")
write = [Depends(same_origin_json)]

_SOURCE = re.compile(r"^[a-z0-9][a-z0-9_.-]{0,39}$")
_HM = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


def notify_key(request: Request) -> None:
    """Senders prove themselves with the shared NOTIFY_KEY header. Without a
    configured key the endpoint stays closed rather than open to the network."""
    expected = ((request.app.state.config.get("telegram") or {}).get("notify_key") or "").strip()
    if not expected:
        raise HTTPException(503, "NOTIFY_KEY is not set on the hub.")
    given = request.headers.get("x-notify-key", "")
    if not hmac.compare_digest(given.encode(), expected.encode()):
        raise HTTPException(401, "Wrong or missing X-Notify-Key.")


class NotifyIn(BaseModel):
    source: Annotated[str, Field(max_length=40)]
    category: str
    severity: core.Severity = "info"
    title: Annotated[str, Field(min_length=1, max_length=200)]
    body: Annotated[str, Field(max_length=3000)] = ""

    @field_validator("source")
    @classmethod
    def _source(cls, value: str) -> str:
        if not _SOURCE.match(value):
            raise ValueError("use lowercase letters, digits, dots, dashes or underscores")
        return value

    @field_validator("category")
    @classmethod
    def _category(cls, value: str) -> str:
        if value not in core.CATEGORIES:
            raise ValueError(f"must be one of: {', '.join(core.CATEGORIES)}")
        return value


@router.post("/notify", dependencies=[Depends(notify_key), Depends(same_origin_json)])
async def notify(body: NotifyIn, request: Request) -> core.AlertMessage:
    """For senders on the NAS: backup.sh, Watchtower, Uptime Kuma."""
    return await core.notify(
        request.app.state.store, request.app.state.config, **body.model_dump()
    )


@router.get("/alerts/messages")
def list_messages(request: Request, limit: int = 100, category: str | None = None) -> Any:
    return core.messages(request.app.state.store, min(max(limit, 1), 500), category)


class QuietHours(BaseModel):
    enabled: bool
    start: str
    end: str

    @field_validator("start", "end")
    @classmethod
    def _time(cls, value: str) -> str:
        if not _HM.match(value):
            raise ValueError("use HH:MM, e.g. 23:00")
        return value


class AlertSettings(BaseModel):
    routing: dict[str, str]
    quiet: QuietHours


def _settings(request: Request) -> dict[str, Any]:
    store, cfg = request.app.state.store, request.app.state.config
    return {
        "routing": core.routing(store),
        "quiet": core.quiet_hours(store),
        "categories": core.CATEGORIES,
        "chats": [
            {"key": key, "label": chat["label"], "configured": bool(chat["id"])}
            for key, chat in core.chats(cfg).items()
        ],
        "token_set": bool(((cfg.get("telegram") or {}).get("token") or "").strip()),
        "notify_key_set": bool(((cfg.get("telegram") or {}).get("notify_key") or "").strip()),
    }


@router.get("/alerts/settings")
def get_settings(request: Request) -> dict[str, Any]:
    return _settings(request)


@router.put("/alerts/settings", dependencies=write)
def put_settings(body: AlertSettings, request: Request) -> dict[str, Any]:
    known_chats = core.chats(request.app.state.config)
    for category, chat in body.routing.items():
        if category not in core.CATEGORIES:
            raise HTTPException(422, f"routing: unknown category {category}")
        if chat not in known_chats:
            raise HTTPException(422, f"routing: unknown chat {chat}")
    store = request.app.state.store
    core.put_setting(store, "routing", body.routing)
    core.put_setting(store, "quiet", body.quiet.model_dump())
    return _settings(request)


class ManualMessage(BaseModel):
    chat: str
    text: Annotated[str, Field(min_length=1, max_length=3000)]


@router.post("/alerts/send", dependencies=write)
async def send(body: ManualMessage, request: Request) -> core.AlertMessage:
    """A message typed on the Alerts page. Goes out right away, quiet hours or not."""
    cfg = request.app.state.config
    if body.chat not in core.chats(cfg):
        raise HTTPException(422, f"chat: unknown chat {body.chat}")
    store = request.app.state.store
    # Route by the chosen chat, not by category: store a one-off routing.
    message = await core.notify(
        store, cfg, source="hub", category="manual", severity="info",
        title=body.text.split("\n", 1)[0][:200],
        body=body.text.split("\n", 1)[1] if "\n" in body.text else "",
        bypass_quiet=True, chat=body.chat,
    )
    return message


class RuleSettings(BaseModel):
    enabled: bool
    threshold_pct: Annotated[float | None, Field(ge=1, le=100)] = None
    unhealthy_minutes: Annotated[int | None, Field(ge=1, le=1440)] = None
    restarts: Annotated[int | None, Field(ge=2, le=100)] = None
    restart_window_minutes: Annotated[int | None, Field(ge=1, le=1440)] = None
    hours: Annotated[int | None, Field(ge=1, le=24 * 14)] = None


def _rules(request: Request) -> dict[str, Any]:
    return {"rules": rules.rule_settings(request.app.state.store), "labels": rules.RULE_LABELS}


@router.get("/alerts/rules")
def get_rules(request: Request) -> dict[str, Any]:
    return _rules(request)


@router.put("/alerts/rules", dependencies=write)
def put_rules(body: dict[str, RuleSettings], request: Request) -> dict[str, Any]:
    """Save rule settings; only the fields a rule has are kept."""
    current = rules.rule_settings(request.app.state.store)
    for name, given in body.items():
        if name not in rules.DEFAULT_RULES:
            raise HTTPException(422, f"unknown rule {name}")
        fields = given.model_dump(exclude_none=True)
        current[name] |= {k: v for k, v in fields.items() if k in rules.DEFAULT_RULES[name]}
    core.put_setting(request.app.state.store, "rules", current)
    return _rules(request)


@router.get("/alerts/incidents")
def list_incidents(request: Request) -> Any:
    """Open incidents first, then recently resolved ones."""
    return rules.incidents(request.app.state.store)
