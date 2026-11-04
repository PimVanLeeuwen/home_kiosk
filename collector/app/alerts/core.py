"""Alert routing, quiet hours, the morning digest, and the message log.

Every message the hub sends, or holds, is logged in `alert_message`; the
Alerts page reads that log. Settings (routing per category, quiet hours, ntfy
on or off) live in `alert_setting`, edited in the app.

With an ntfy token set and ntfy switched on (M31), messages go to the NAS's
ntfy, one topic per category, and Telegram only gets them when ntfy fails.
Quiet hours then deliver silently instead of holding; replies to a Telegram
message (the bot, the explainers) stay on Telegram.
"""

from __future__ import annotations

import html
import json
import logging
from collections.abc import Callable
from datetime import UTC, datetime, time, timedelta
from typing import Any, Literal
from zoneinfo import ZoneInfo

from PIL import Image
from pydantic import BaseModel

from .. import paint_notify
from ..store import Store
from . import ntfy as ntfy_api
from .ntfy import Ntfy
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
    -- sending (only while it goes out), sent, quiet (sent silently in quiet
    -- hours, ntfy), held (quiet hours, Telegram), digested, failed
    status   TEXT NOT NULL,
    error    TEXT,
    sent_at  TEXT
);
CREATE INDEX IF NOT EXISTS alert_message_ts ON alert_message (ts);

-- A message's picture (M31 step 4), for its page; kept as long as the page.
CREATE TABLE IF NOT EXISTS alert_picture (
    message_id INTEGER PRIMARY KEY,
    ts         TEXT NOT NULL,
    jpeg       BLOB NOT NULL
);

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
    # What the owner set to remember on a day (app/reminders.py, plan.md M32).
    "reminders": "Reminders",
    "manual": "Sent from the hub",
}

DEFAULT_ROUTING = {category: "nas" for category in CATEGORIES} | {"portfolio": "portfolio"}
DEFAULT_QUIET = {"enabled": True, "start": "23:00", "end": "07:00"}

LEVEL = {"error": "ERROR", "warning": "WARNING", "ok": "OK", "info": "INFO"}

DIGEST_LIMIT = 20
# A message's page and its picture stay this long (M31).
PAGE_DAYS = 7


class AlertMessage(BaseModel):
    id: int
    ts: datetime
    source: str
    category: str
    severity: Severity
    title: str
    body: str
    chat: str
    status: Literal["sending", "sent", "quiet", "held", "digested", "failed"]
    error: str | None
    sent_at: datetime | None
    telegram_id: int | None = None  # Telegram's id for the sent message
    channel: Literal["ntfy", "telegram"] | None = None  # None: held or failed
    ntfy_id: str | None = None
    # For the message's page (M31): the Telegram HTML, and a rule's incident key.
    html: str | None = None
    incident: str | None = None


def ensure_tables(store: Store) -> None:
    with store.connect() as conn:
        conn.executescript(TABLES)
        columns = {r["name"] for r in conn.execute("PRAGMA table_info(alert_message)")}
        if "telegram_id" not in columns:
            # Added for the alert explainer (M26), which replies to the alert's message.
            conn.execute("ALTER TABLE alert_message ADD COLUMN telegram_id INTEGER")
        if "channel" not in columns:
            # Added for ntfy (M31); older rows all went to Telegram.
            conn.execute("ALTER TABLE alert_message ADD COLUMN channel TEXT")
            conn.execute("UPDATE alert_message SET channel = 'telegram' "
                         "WHERE status IN ('sent', 'digested')")
            conn.execute("ALTER TABLE alert_message ADD COLUMN ntfy_id TEXT")
        if "html" not in columns:
            # Added for the message's page (M31 step 3).
            conn.execute("ALTER TABLE alert_message ADD COLUMN html TEXT")
            conn.execute("ALTER TABLE alert_message ADD COLUMN incident TEXT")
            conn.execute("ALTER TABLE alert_message ADD COLUMN explanation TEXT")


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


def ntfy_configured(cfg: dict[str, Any]) -> bool:
    ntfy = cfg.get("ntfy") or {}
    return bool(str(ntfy.get("url") or "").strip() and str(ntfy.get("token") or "").strip())


def ntfy_enabled(store: Store) -> bool:
    """The switch in Settings, Alerts; on until switched off."""
    return bool(get_setting(store, "ntfy", True))


def ntfy_on(store: Store, cfg: dict[str, Any]) -> bool:
    return ntfy_configured(cfg) and ntfy_enabled(store)


def click_url(cfg: dict[str, Any], message_id: int | None = None) -> str | None:
    """Where a tap on a notification leads: the message's own page in the hub
    (`hub.url`), or the Alerts page without an id."""
    url = str((cfg.get("hub") or {}).get("url") or "").strip().rstrip("/")
    if not url.startswith(("https://", "http://")):
        return None
    return f"{url}/alerts/{message_id}" if message_id is not None else f"{url}/alerts"


def priority(severity: str, category: str, quiet: bool, bypass_quiet: bool) -> int:
    """Errors are Time Sensitive; in quiet hours the rest arrives silently, except
    what is sent through them on purpose (the train, a typed message). The
    morning briefing is quiet too: it comes at 06:30."""
    if severity == "error":
        return ntfy_api.URGENT
    if quiet and (not bypass_quiet or category == "briefing"):
        return ntfy_api.QUIET
    return ntfy_api.NORMAL


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
            "status, error, sent_at, telegram_id, channel, ntfy_id, html, incident) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (now.isoformat(), fields["source"], fields["category"], fields["severity"],
             fields["title"], fields.get("body", ""), fields["chat"], fields["status"],
             fields.get("error"), fields.get("sent_at"), fields.get("telegram_id"),
             fields.get("channel"), fields.get("ntfy_id"), fields.get("html"),
             fields.get("incident")),
        )
        row = conn.execute("SELECT * FROM alert_message WHERE id = ?", (cur.lastrowid,)).fetchone()
    return AlertMessage.model_validate(dict(row))


_FINAL = ("status", "error", "sent_at", "telegram_id", "channel", "ntfy_id")


def finish_entry(store: Store, message_id: int, **fields: Any) -> AlertMessage:
    """Settle a logged message: what happened to it (`_FINAL` fields only)."""
    names = [k for k in _FINAL if k in fields]
    with store.connect() as conn:
        conn.execute(f"UPDATE alert_message SET {', '.join(f'{k} = ?' for k in names)} "
                     "WHERE id = ?", (*(fields[k] for k in names), message_id))
        row = conn.execute("SELECT * FROM alert_message WHERE id = ?", (message_id,)).fetchone()
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
    ntfy: Ntfy | None = None,
    incident: str | None = None,
    picture: Callable[[], Image.Image | None] | None = None,
) -> AlertMessage:
    """Route (or use `chat`), then send through ntfy, or through Telegram (held in
    quiet hours) when ntfy is off or fails, and log one message.
    `formatted` is ready-made Telegram HTML to send instead of title and body;
    `reply_to` a sent message's Telegram id to answer (the alert explainer), which
    keeps it on Telegram; `buttons` a row of buttons under it, answered by the bot
    (bot.py), shown on Telegram only; `incident` a rule's incident key, for the
    message's page; `picture` paints the message's picture (M31 step 4), sent with it
    through ntfy and kept for its page; a picture that fails is left out. The message
    is logged first, so a tap can lead to its page."""
    now = now or datetime.now(UTC)
    chat_key = chat or routing(store).get(category, "nas")
    html_text = formatted or format_html(severity, title, body)
    entry = log_entry(store, now, source=source, category=category, severity=severity,
                      title=title, body=body, chat=chat_key, status="sending", html=html_text,
                      incident=incident)
    quiet = in_quiet_hours(local(now, cfg), quiet_hours(store))
    jpeg = _picture(store, entry.id, now, picture) if picture else None

    ntfy_failed = None
    if reply_to is None and (ntfy is not None or ntfy_on(store, cfg)):
        level = priority(severity, category, quiet, bypass_quiet)
        try:
            publisher = ntfy or Ntfy(**{k: str((cfg.get("ntfy") or {}).get(k) or "")
                                        for k in ("url", "token")})
            # The template's first line is the title, so the text is what follows.
            message = (ntfy_api.plain(formatted).partition("\n")[2].strip() if formatted
                       else body.strip())
            # ntfy wants a message: a title alone goes as the message, under the
            # category's name.
            answer = await publisher.publish(
                ntfy_api.topic(category),
                title if message else CATEGORIES.get(category, category),
                message or title, priority=level,
                tags=[ntfy_api.DOT.get(severity, "white_circle")],
                click=click_url(cfg, entry.id), picture=jpeg)
        except Exception as exc:
            ntfy_failed = ntfy_api.describe(exc)
            log.warning("ntfy publish for %s failed: %s", source, type(exc).__name__)
        else:
            status = "quiet" if level == ntfy_api.QUIET and category != "briefing" else "sent"
            return finish_entry(store, entry.id, status=status, sent_at=now.isoformat(),
                                channel="ntfy", ntfy_id=str(answer.get("id")))

    note = f"ntfy failed: {ntfy_failed}" if ntfy_failed else None
    if not bypass_quiet and severity != "error" and quiet:
        return finish_entry(store, entry.id, status="held", error=note)

    chat_id = chats(cfg).get(chat_key, {}).get("id")
    try:
        if not chat_id:
            raise ValueError(f"No chat id set for {chat_key}")
        client = telegram or Telegram((cfg.get("telegram") or {}).get("token", ""))
        text = html_text
        extra: dict[str, Any] = {}
        if reply_to is not None:
            extra["reply_to"] = reply_to
        if buttons:
            extra["buttons"] = buttons
        result = await client.send(chat_id, text, **extra)
    except Exception as exc:
        reason = str(exc) if isinstance(exc, ValueError) else describe(exc)
        log.warning("telegram send for %s failed: %s", source, type(exc).__name__)
        if ntfy_failed:
            reason = f"ntfy: {ntfy_failed}; Telegram: {reason}"[:300]
        return finish_entry(store, entry.id, status="failed", error=reason)
    message_id = result.get("message_id") if isinstance(result, dict) else None
    return finish_entry(store, entry.id, status="sent", sent_at=now.isoformat(),
                        telegram_id=message_id, channel="telegram", error=note)


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


def _picture(store: Store, message_id: int, now: datetime,
             paint: Callable[[], Image.Image | None]) -> bytes | None:
    """Paint, keep and return a message's picture as JPEG; None when there is none or
    painting failed (the message goes without). Pictures older than a page are dropped."""
    try:
        image = paint()
        if image is None:
            return None
        data = paint_notify.jpeg(image)
    except Exception as exc:
        log.warning("picture for message %s failed: %s", message_id, type(exc).__name__)
        return None
    with store.connect() as conn:
        conn.execute("DELETE FROM alert_picture WHERE ts < ?",
                     ((now - timedelta(days=PAGE_DAYS + 1)).isoformat(),))
        conn.execute("INSERT OR REPLACE INTO alert_picture (message_id, ts, jpeg) VALUES (?, ?, ?)",
                     (message_id, now.isoformat(), data))
    return data


def picture(store: Store, message_id: int) -> bytes | None:
    with store.connect() as conn:
        row = conn.execute("SELECT jpeg FROM alert_picture WHERE message_id = ?",
                           (message_id,)).fetchone()
    return bytes(row["jpeg"]) if row else None


def quiet_since(store: Store, since: datetime, chat: str | None = None) -> list[dict[str, Any]]:
    """Messages ntfy delivered silently in quiet hours since `since`, oldest first;
    for one chat (the routing) when given. The briefing summarises them (M31)."""
    query = "SELECT * FROM alert_message WHERE status = 'quiet' AND ts >= ?"
    args: tuple[str, ...] = (since.isoformat(),)
    if chat:
        query, args = query + " AND chat = ?", (*args, chat)
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
