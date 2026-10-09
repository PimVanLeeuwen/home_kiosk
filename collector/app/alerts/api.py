"""Endpoints for senders (/api/notify) and the Alerts page (/api/alerts/*)."""

from __future__ import annotations

import hmac
import re
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field, field_validator, model_validator

from ..security import same_origin_json
from . import core, formats, rules, templates

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
    # Optional: without one, the first line of the body is the title
    # (Watchtower's report starts with its summary line).
    title: Annotated[str, Field(max_length=200)] = ""
    body: Annotated[str, Field(max_length=3000)] = ""
    # Figures for the hub's own template (backup.sh sends these); title and
    # body are what goes out when they are missing or unreadable.
    data: dict[str, Any] | None = None

    @model_validator(mode="after")
    def _title(self) -> NotifyIn:
        if not self.title.strip():
            first, _, rest = self.body.strip().partition("\n")
            if not first.strip():
                raise ValueError("give a title or a body")
            self.title, self.body = first.strip()[:200], rest.strip()
        return self

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
    store = request.app.state.store
    fields = body.model_dump(exclude={"data"})
    sent = formats.from_sender(store, body.source, body.severity, body.title, body.body, body.data)
    if sent is not None:
        fields |= {"title": sent.title, "body": sent.body, "formatted": sent.html}
    return await core.notify(store, request.app.state.config, **fields)


# Uptime Kuma heartbeat states (src/util.ts in Kuma).
KUMA_STATUS: dict[int, tuple[core.Severity, str]] = {
    0: ("error", "is down"),
    1: ("ok", "is up"),
    2: ("warning", "is pending"),
    3: ("info", "is in maintenance"),
}


@router.post("/notify/kuma", dependencies=[Depends(notify_key), Depends(same_origin_json)])
async def notify_kuma(payload: dict[str, Any], request: Request) -> core.AlertMessage:
    """Uptime Kuma's Webhook notification (body: application/json). It sends
    {heartbeat, monitor, msg}; heartbeat and monitor are null for a test."""
    heartbeat = payload.get("heartbeat") or {}
    monitor = payload.get("monitor") or {}
    message = str(payload.get("msg") or "")[:3000]
    store = request.app.state.store
    if heartbeat and monitor:
        severity, state = KUMA_STATUS.get(int(heartbeat.get("status", 0)), ("info", "changed"))
        sent = templates.message(store, "kuma", {
            "monitor": str(monitor.get("name") or "A monitor")[:150], "state": state,
            "message": str(heartbeat.get("msg") or "")[:3000]}, severity)
        title, body, formatted = sent.title, sent.body, sent.html
    else:
        severity, title, body = "info", "Uptime Kuma", message or "Test notification"
        formatted = None
    return await core.notify(
        store, request.app.state.config, source="uptime-kuma", category="uptime",
        severity=severity, title=title, body=body, formatted=formatted,
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
    restore_days: Annotated[int | None, Field(ge=1, le=366)] = None


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


# --- message templates (Settings → Messages) -----------------------------------------


class TemplateText(BaseModel):
    text: Annotated[str, Field(max_length=templates.MAX_TEXT)]


def _template(store: Any, template_id: str) -> dict[str, Any]:
    t = templates.CATALOG[template_id]
    text = templates.text_of(store, template_id)
    return {
        "id": template_id,
        "group": t.group,
        "label": t.label,
        "description": t.description,
        "parent": t.parent or None,
        "category": core.CATEGORIES.get(t.category) if t.category else None,
        "placeholders": [
            {"name": name, "description": what, "block": name in t.blocks}
            for name, (what, _) in t.placeholders.items()
        ],
        "default": t.default,
        "text": text,
        "customised": text != t.default,
        "preview": templates.sample(template_id, store=store).html,
    }


def _known(template_id: str) -> None:
    if template_id not in templates.CATALOG:
        raise HTTPException(404, f"No message template called {template_id}.")


@router.get("/alerts/templates")
def list_templates(request: Request) -> list[dict[str, Any]]:
    return [_template(request.app.state.store, tid) for tid in templates.CATALOG]


@router.put("/alerts/templates/{template_id}", dependencies=write)
def put_template(template_id: str, body: TemplateText, request: Request) -> dict[str, Any]:
    _known(template_id)
    try:
        templates.save(request.app.state.store, template_id, body.text)
    except templates.TemplateError as exc:
        raise HTTPException(422, str(exc)) from None
    return _template(request.app.state.store, template_id)


@router.delete("/alerts/templates/{template_id}", dependencies=write)
def reset_template(template_id: str, request: Request) -> dict[str, Any]:
    _known(template_id)
    templates.reset(request.app.state.store, template_id)
    return _template(request.app.state.store, template_id)


@router.post("/alerts/templates/{template_id}/preview", dependencies=write)
def preview_template(template_id: str, body: TemplateText, request: Request) -> dict[str, Any]:
    """The draft with sample values, for the editor. A problem is reported, not raised."""
    _known(template_id)
    try:
        templates.check(template_id, body.text)
        error = None
    except templates.TemplateError as exc:
        error = str(exc)
    sent = templates.sample(template_id, {template_id: body.text}, request.app.state.store)
    return {"html": sent.html, "error": error}


@router.post("/alerts/templates/{template_id}/test", dependencies=write)
async def test_template(template_id: str, body: TemplateText,
                        request: Request) -> core.AlertMessage:
    """Send the draft with sample values to the chat its message goes to, now."""
    _known(template_id)
    try:
        templates.check(template_id, body.text)
    except templates.TemplateError as exc:
        raise HTTPException(422, str(exc)) from None
    store = request.app.state.store
    target = templates.CATALOG[templates.CATALOG[template_id].parent or template_id]
    sent = templates.sample(template_id, {template_id: body.text}, store)
    return await core.notify(
        store, request.app.state.config, source="hub.test", category=target.category,
        severity=target.severity, title=f"Test: {sent.title}"[:200], body=sent.body,
        formatted=sent.html, bypass_quiet=True,
    )
