"""A message's own page (plan.md M31 step 3): what a tap on a notification opens.

`/alerts/{id}` shows a message for 7 days: its full text (the Telegram HTML),
whether its problem is still open, the way onward (hub pages and services), the
same rule's or source's earlier messages, and an explanation on request for
warnings and errors, kept with the message once asked. After 7 days the page
only says the message has expired; the message stays in the log.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from .. import ai, explain_open, explainer
from ..store import Store
from . import core, rules

log = logging.getLogger(__name__)

KEEP = timedelta(days=7)
EARLIER_LIMIT = 10
EXPLAINED = ("warning", "error")

# Hub pages and services per kind of message: (label, hub page) or (label,
# service id, path in the service, hint). The web makes the service's address.
_PAGES: dict[str, list[tuple[str, ...]]] = {
    "rule.disk_space": [("NAS page", "/nas", "storage")],
    "rule.smart": [("NAS page", "/nas", "disks"), ("Scrutiny", "@scrutiny", "/", "disk health")],
    "rule.storage_box": [("Backups page", "/backups", "storage box")],
    "rule.backup_missing": [("Backups page", "/backups", "")],
    "rule.token_expiry": [("Repos page", "/repos", "tokens")],
    "rule.adguard": [("AdGuard Home", "@adguard", "/", "")],
    "rule.outside_services": [("Home", "/", "outside services")],
    "rule.apple_offline": [("Home", "/", "Apple devices")],
    "rule.desk_panels": [("Desk panels", "/settings/desk-panels", "")],
    "rule.train": [("Home", "/", "your train")],
    "rule.portfolio_move": [("Portfolio page", "/portfolio", ""),
                            ("Ghostfolio", "@ghostfolio", "/", "")],
    "backup": [("Backups page", "/backups", "")],
    "github-mirror": [("Backups page", "/backups", "GitHub mirror"), ("Repos page", "/repos", "")],
    "watchtower": [("Docker page", "/docker", "updates")],
    "pinned": [("Docker page", "/docker", "pinned images")],
    "uptime-kuma": [("Uptime Kuma", "@uptime-kuma", "/", "")],
    "briefing": [("Home", "/", "")],
    "ai": [("AI settings", "/settings/ai", "")],
}
_CATEGORIES: dict[str, list[tuple[str, ...]]] = {
    "portfolio": [("Portfolio page", "/portfolio", ""), ("Ghostfolio", "@ghostfolio", "/", "")],
    "paperless": [("Paperless", "@paperless", "/", "")],
    "updates": [("Docker page", "/docker", "")],
    "backup": [("Backups page", "/backups", "")],
    "train": [("Home", "/", "your train")],
}


def _link(entry: tuple[str, ...]) -> dict[str, str]:
    label, target, *rest = entry
    if target.startswith("@"):
        path, hint = (rest + ["/", ""])[:2]
        return {"label": label, "service": target[1:], "path": path, "hint": hint}
    return {"label": label, "page": target, "hint": rest[0] if rest else ""}


def links(message: dict[str, Any]) -> list[dict[str, str]]:
    """Where to go from a message: a container's logs, the hub page it is about."""
    incident = message.get("incident") or ""
    kind, _, name = incident.partition(":")
    if kind in ("unhealthy", "down") and name:
        return [{"label": "Logs in Dozzle", "service": "dozzle", "path": f"/show?name={name}",
                 "hint": name},
                {"label": "Docker page", "page": "/docker", "hint": ""}]
    found = _PAGES.get(message["source"]) or _CATEGORIES.get(message["category"]) or []
    return [_link(entry) for entry in found]


def _state(store: Store, incident: str | None) -> dict[str, Any] | None:
    if not incident:
        return None
    with store.connect() as conn:
        row = conn.execute("SELECT opened_at, resolved_at FROM alert_incident WHERE key = ?",
                           (incident,)).fetchone()
    if row is None:
        return None
    return {"open": row["resolved_at"] is None, "opened_at": row["opened_at"],
            "resolved_at": row["resolved_at"]}


def _earlier(store: Store, message: dict[str, Any], since: datetime) -> list[dict[str, Any]]:
    """The same incident's messages, or else the same source's, in the last 7 days,
    newest first, this one included."""
    key, value = (("incident", message["incident"]) if message.get("incident")
                  else ("source", message["source"]))
    with store.connect() as conn:
        rows = conn.execute(
            f"SELECT id, ts, severity, title FROM alert_message WHERE {key} = ? AND ts >= ? "
            "AND status != 'sending' ORDER BY ts DESC, id DESC LIMIT ?",
            (value, since.isoformat(), EARLIER_LIMIT)).fetchall()
    return [dict(r) for r in rows]


def _row(store: Store, message_id: int) -> dict[str, Any] | None:
    with store.connect() as conn:
        row = conn.execute("SELECT * FROM alert_message WHERE id = ?", (message_id,)).fetchone()
    return dict(row) if row else None


def _explanation(row: dict[str, Any]) -> dict[str, Any] | None:
    try:
        return json.loads(row["explanation"]) if row.get("explanation") else None
    except json.JSONDecodeError:
        return None


def _expired(row: dict[str, Any], now: datetime) -> bool:
    return datetime.fromisoformat(row["ts"]) < now - KEEP


def can_explain(cfg: dict[str, Any], store: Store, row: dict[str, Any]) -> bool:
    return row["severity"] in EXPLAINED and explain_open.available(cfg, store)


def page(cfg: dict[str, Any], store: Store, message_id: int,
         now: datetime | None = None) -> dict[str, Any] | None:
    """The page's content; None for no such message, a short answer once expired."""
    now = now or datetime.now(UTC)
    row = _row(store, message_id)
    if row is None:
        return None
    sent = datetime.fromisoformat(row["ts"])
    if _expired(row, now):
        return {"id": row["id"], "ts": row["ts"], "expired": True}
    message = core.AlertMessage.model_validate(row).model_dump(mode="json")
    return message | {
        "expired": False,
        "expires_at": (sent + KEEP).isoformat(),
        "html": row.get("html") or core.format_html(row["severity"], row["title"], row["body"]),
        "state": _state(store, row.get("incident")),
        "earlier": _earlier(store, row, now - KEEP),
        "links": links(row),
        "explanation": _explanation(row),
        "can_explain": can_explain(cfg, store, row),
    }


class ExplainError(Exception):
    """Why a message gets no explanation, fit for the page."""


async def explain(cfg: dict[str, Any], store: Store, message_id: int,
                  now: datetime | None = None,
                  claude: ai.ClientFactory | None = None) -> dict[str, Any]:
    """Explain one message and keep the answer with it; a kept answer is returned as
    it is. Same data as "Explain warnings" (M29): the message's own title and text,
    redacted, how long its problem has been open, and the NAS's storage and memory."""
    now = now or datetime.now(UTC)
    row = _row(store, message_id)
    if row is None or _expired(row, now):
        raise ExplainError("No such message, or it has expired.")
    if kept := _explanation(row):
        return kept
    if not can_explain(cfg, store, row):
        raise ExplainError("Explanations are for warnings and errors, with the Alert "
                           "explainer on in Settings, AI.")
    state = _state(store, row.get("incident"))
    open_for = (f", open {rules._duration(state['opened_at'], now)}"
                if state and state["open"] else "")
    lines = [f"1. [{core.LEVEL.get(row['severity'], '')}{open_for}] "
             f"{explainer.redact(row['title'])}"]
    if row.get("body"):
        lines.append("   " + explainer.redact(row["body"]).replace("\n", "\n   "))
    prompt = ("Open alerts:\n" + "\n".join(lines)
              + f"\n\nThe server:\n{explainer.house(store) or 'unknown'}")
    answer = await ai.ask(cfg, store, feature=explainer.FEATURE, model=ai.EXPLAINER_MODEL,
                          system=explain_open.SYSTEM, prompt=prompt, max_tokens=2048,
                          effort="medium", schema=explain_open.SCHEMA, fallback=True, now=now,
                          client=claude)
    if answer is None:
        raise ExplainError("Claude did not answer (off, the monthly cap, or a failure).")
    try:
        item = json.loads(answer)["alerts"][0]
        kept = {"cause": str(item["cause"]).strip(), "todo": str(item["todo"]).strip(),
                "asked_at": now.isoformat()}
    except (json.JSONDecodeError, KeyError, IndexError, TypeError):
        log.warning("message explain: the answer is not the expected JSON")
        raise ExplainError("Claude's answer could not be read.") from None
    with store.connect() as conn:
        conn.execute("UPDATE alert_message SET explanation = ? WHERE id = ?",
                     (json.dumps(kept), message_id))
    return kept
