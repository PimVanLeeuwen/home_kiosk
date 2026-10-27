"""Alert routing, quiet hours, the morning digest, and the message log.

Every message the hub sends, or holds, is logged in `alert_message`; the
Alerts page reads that log. Settings (routing per category, quiet hours) live
in `alert_setting`, edited in the app.
"""

from __future__ import annotations

import html
import json
import logging
from datetime import UTC, datetime, time
from typing import Any, Literal
from zoneinfo import ZoneInfo

from pydantic import BaseModel

from ..store import Store
from .telegram import Telegram, describe

log = logging.getLogger(__name__)

TABLES = """
CREATE TABLE IF NOT EXISTS alert_message (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    ts       TEXT NOT NULL,
    source   TEXT NOT NULL,
    category TEXT NOT NULL,
    severity TEXT NOT NULL,
    title    TEXT NOT NULL,
    body     TEXT NOT NULL DEFAULT '',
    chat     TEXT NOT NULL,
    -- sent, held (quiet hours), digested, failed
    status   TEXT NOT NULL,
    error    TEXT,
    sent_at  TEXT
);
CREATE INDEX IF NOT EXISTS alert_message_ts ON alert_message (ts);

CREATE TABLE IF NOT EXISTS alert_setting (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""

Severity = Literal["info", "ok", "warning", "error"]

CATEGORIES = {
    "backup": "Backups",
    "updates": "Container updates",
    "uptime": "Uptime Kuma",
    "rules": "Hub alert rules",
    "portfolio": "Portfolio",
    "train": "Your train",
    # New senders of bills for Paperless (nas-docker host-jobs/paperless-senders.sh).
    "paperless": "Paperless",
    # The AI spend nearing its monthly cap (app/ai.py).
    "ai": "AI",
    # The morning digest, weekdays at 06:30 (app/briefing.py).
    "briefing": "Morning digest",
    "manual": "Sent from the hub",
}

DEFAULT_ROUTING = {category: "nas" for category in CATEGORIES} | {"portfolio": "portfolio"}
DEFAULT_QUIET = {"enabled": True, "start": "23:00", "end": "07:00"}

LEVEL = {"error": "ERROR", "warning": "WARNING", "ok": "OK", "info": "INFO"}

DIGEST_LIMIT = 20


class AlertMessage(BaseModel):
    id: int
    ts: datetime
    source: str
    category: str
    severity: Severity
    title: str
    body: str
    chat: str
    status: Literal["sent", "held", "digested", "failed"]
    error: str | None
    sent_at: datetime | None
    telegram_id: int | None = None  # Telegram's id for the sent message


def ensure_tables(store: Store) -> None:
    with store.connect() as conn:
        conn.executescript(TABLES)
        columns = {r["name"] for r in conn.execute("PRAGMA table_info(alert_message)")}
        if "telegram_id" not in columns:
            # Added for the alert explainer (M26), which replies to the alert's message.
            conn.execute("ALTER TABLE alert_message ADD COLUMN telegram_id INTEGER")


# --- settings -------------------------------------------------------------------


def get_setting(store: Store, key: str, default: Any) -> Any:
    with store.connect() as conn:
        row = conn.execute("SELECT value FROM alert_setting WHERE key = ?", (key,)).fetchone()
    return json.loads(row["value"]) if row else default


def put_setting(store: Store, key: str, value: Any) -> None:
    with store.connect() as conn:
        conn.execute(
            "INSERT INTO alert_setting (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, json.dumps(value)),
        )


def routing(store: Store) -> dict[str, str]:
    return DEFAULT_ROUTING | get_setting(store, "routing", {})


def quiet_hours(store: Store) -> dict[str, Any]:
    return DEFAULT_QUIET | get_setting(store, "quiet", {})


def chats(cfg: dict[str, Any]) -> dict[str, dict[str, str]]:
    """Configured chats by key, e.g. {"nas": {"id": "-50..", "label": "NAS alerts"}}."""
    return {
        key: {"id": str(c.get("id") or "").strip(), "label": c.get("label", key)}
        for key, c in ((cfg.get("telegram") or {}).get("chats") or {}).items()
    }


# --- quiet hours ------------------------------------------------------------------


def _hm(value: str) -> time:
    hour, minute = (int(part) for part in value.split(":"))
    return time(hour, minute)


def in_quiet_hours(local_now: datetime, quiet: dict[str, Any]) -> bool:
    if not quiet.get("enabled"):
        return False
    start, end, now = _hm(quiet["start"]), _hm(quiet["end"]), local_now.time()
    if start == end:
        return False
    if start < end:
        return start <= now < end
    return now >= start or now < end  # the window crosses midnight


def local(now: datetime, cfg: dict[str, Any]) -> datetime:
    return now.astimezone(ZoneInfo(cfg.get("timezone", "UTC")))


# --- sending ---------------------------------------------------------------------


def format_html(severity: str, title: str, body: str = "") -> str:
    level = LEVEL.get(severity)
    text = f"<b>{level}</b> · " if level else ""
    text += f"<b>{html.escape(title)}</b>"
    if body:
        text += f"\n{html.escape(body)}"
    return text


def log_entry(store: Store, now: datetime, **fields: Any) -> AlertMessage:
    with store.connect() as conn:
        cur = conn.execute(
            "INSERT INTO alert_message (ts, source, category, severity, title, body, chat, "
            "status, error, sent_at, telegram_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (now.isoformat(), fields["source"], fields["category"], fields["severity"],
             fields["title"], fields.get("body", ""), fields["chat"], fields["status"],
             fields.get("error"), fields.get("sent_at"), fields.get("telegram_id")),
        )
        row = conn.execute("SELECT * FROM alert_message WHERE id = ?", (cur.lastrowid,)).fetchone()
    return AlertMessage.model_validate(dict(row))


async def notify(
    store: Store,
    cfg: dict[str, Any],
    *,
    source: str,
    category: str,
    severity: Severity,
    title: str,
    body: str = "",
    bypass_quiet: bool = False,
    chat: str | None = None,
    now: datetime | None = None,
    telegram: Telegram | None = None,
    formatted: str | None = None,
    reply_to: int | None = None,
    buttons: list[dict[str, str]] | None = None,
) -> AlertMessage:
    """Route (or use `chat`), hold for quiet hours or send, and log one message.
    `formatted` is ready-made Telegram HTML to send instead of title and body;
    `reply_to` a sent message's Telegram id to answer (the alert explainer);
    `buttons` a row of buttons under it, answered by the bot (bot.py)."""
    now = now or datetime.now(UTC)
    chat_key = chat or routing(store).get(category, "nas")
    fields = {"source": source, "category": category, "severity": severity,
              "title": title, "body": body, "chat": chat_key}

    held = (
        not bypass_quiet
        and severity != "error"
        and in_quiet_hours(local(now, cfg), quiet_hours(store))
    )
    if held:
        return log_entry(store, now, **fields, status="held")

    chat_id = chats(cfg).get(chat_key, {}).get("id")
    try:
        if not chat_id:
            raise ValueError(f"No chat id set for {chat_key}")
        client = telegram or Telegram((cfg.get("telegram") or {}).get("token", ""))
        text = formatted or format_html(severity, title, body)
        extra: dict[str, Any] = {}
        if reply_to is not None:
            extra["reply_to"] = reply_to
        if buttons:
            extra["buttons"] = buttons
        result = await client.send(chat_id, text, **extra)
    except Exception as exc:
        reason = str(exc) if isinstance(exc, ValueError) else describe(exc)
        log.warning("telegram send for %s failed: %s", source, type(exc).__name__)
        return log_entry(store, now, **fields, status="failed", error=reason)
    message_id = result.get("message_id") if isinstance(result, dict) else None
    return log_entry(store, now, **fields, status="sent", sent_at=now.isoformat(),
                     telegram_id=message_id)


async def send_digests(
    store: Store, cfg: dict[str, Any], now: datetime | None = None,
    telegram: Telegram | None = None,
) -> int:
    """After quiet hours: one summary per chat of what was held. Returns how
    many digests went out."""
    now = now or datetime.now(UTC)
    if in_quiet_hours(local(now, cfg), quiet_hours(store)):
        return 0
    by_chat: dict[str, list[dict[str, Any]]] = {}
    for message in held(store):
        by_chat.setdefault(message["chat"], []).append(message)

    sent = 0
    for chat_key, messages in by_chat.items():
        lines = [f"{LEVEL.get(m['severity'], '•')} · {html.escape(m['title'])}"
                 for m in messages[:DIGEST_LIMIT]]
        if len(messages) > DIGEST_LIMIT:
            lines.append(f"… and {len(messages) - DIGEST_LIMIT} more on the Alerts page")
        text = f"<b>While you slept ({len(messages)})</b>\n" + "\n".join(lines)
        chat_id = chats(cfg).get(chat_key, {}).get("id")
        try:
            if not chat_id:
                raise ValueError(f"No chat id set for {chat_key}")
            client = telegram or Telegram((cfg.get("telegram") or {}).get("token", ""))
            await client.send(chat_id, text)
        except Exception as exc:
            # Stay held: the next run tries again.
            log.warning("digest for %s failed: %s", chat_key, type(exc).__name__)
            continue
        mark_digested(store, [m["id"] for m in messages], now)
        sent += 1
    return sent


def held(store: Store, chat: str | None = None) -> list[dict[str, Any]]:
    """Messages held in quiet hours and not yet digested, oldest first; for one
    chat when given."""
    query = "SELECT * FROM alert_message WHERE status = 'held'"
    args: tuple[str, ...] = ()
    if chat:
        query, args = query + " AND chat = ?", (chat,)
    with store.connect() as conn:
        return [dict(r) for r in conn.execute(query + " ORDER BY ts, id", args)]


def mark_digested(store: Store, ids: list[int], now: datetime) -> None:
    """Held messages that went out in a summary (the digest or the morning briefing)."""
    with store.connect() as conn:
        conn.executemany(
            "UPDATE alert_message SET status = 'digested', sent_at = ? WHERE id = ?",
            [(now.isoformat(), i) for i in ids],
        )


def messages(store: Store, limit: int = 100, category: str | None = None) -> list[AlertMessage]:
    query, args = "SELECT * FROM alert_message", []
    if category:
        query, args = query + " WHERE category = ?", [category]
    with store.connect() as conn:
        rows = conn.execute(f"{query} ORDER BY ts DESC, id DESC LIMIT ?", (*args, limit))
        return [AlertMessage.model_validate(dict(r)) for r in rows]
