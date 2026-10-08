"""The Telegram bot: /status, /backup and /portfolio, answered in the two
configured chats only.

Long polling (getUpdates) from inside the collector, so no public webhook is
needed. The update offset is saved, so a restart does not answer old commands
again. Replies are built from the hub's cached data, never fetched on demand.
"""

from __future__ import annotations

import asyncio
import html
import logging
from datetime import UTC, datetime
from typing import Any

from ..portfolio.moves import day_move
from ..store import Store
from . import core, rules
from .telegram import Telegram

log = logging.getLogger(__name__)

POLL_SECONDS = 25
COMMANDS = {
    "status": "NAS health, containers and open alerts",
    "backup": "Last backup per volume and the next run",
    "portfolio": "Portfolio value and today's movers",
}
OFFSET_KEY = "bot_offset"


def _nl(n: float, digits: int = 0) -> str:
    """Dutch number formatting, like the hub: 9.119 and 0,76."""
    text = f"{n:,.{digits}f}"
    return text.replace(",", "§").replace(".", ",").replace("§", ".")


def _when(iso: str, cfg: dict[str, Any]) -> str:
    return core.local(datetime.fromisoformat(iso), cfg).strftime("%a %d %b %H:%M")


# --- replies -------------------------------------------------------------------------


def status_text(store: Store, cfg: dict[str, Any]) -> str:
    nas = store.get_cache("nas")
    if not nas:
        return "<b>NAS</b>\nNo NAS data yet."
    lines = [f"<b>{html.escape(nas['host'])}</b>"]
    temp = f" · {round(nas['cpu_temp_c'])} °C" if nas.get("cpu_temp_c") is not None else ""
    lines.append(f"CPU {round(nas['cpu_pct'])}% · memory {round(nas['ram_pct'])}%{temp}")
    lines.append(f"Containers {nas['containers']['running']} of {nas['containers']['total']} "
                 "running")
    pools = nas["storage"]["pools"][:3]
    if pools:
        lines.append("Fullest: " + ", ".join(
            f"{html.escape(p['name'])} {_nl(p['used_pct'], 0)}%" for p in pools))
    open_now = rules.open_incidents(store)
    if open_now:
        lines.append(f"\n<b>{len(open_now)} open</b>")
        lines += [f"• {html.escape(i['title'])}" for i in open_now.values()]
    else:
        lines.append("\nNothing needs a look")
    if nas.get("stale"):
        lines.append("<i>Figures are out of date.</i>")
    return "\n".join(lines)


def backup_text(store: Store, cfg: dict[str, Any]) -> str:
    history = store.get_cache("backups") or {}
    runs = history.get("runs") or []
    if runs:
        last = runs[0]
        head = "Succeeded" if last["ok"] else "Failed"
        lines = [f"<b>Last backup: {head}</b>", _when(last["finished"], cfg)]
        for v in last["volumes"]:
            minutes = max(1, round(v["seconds"] / 60))
            if v["ok"]:
                size = f" · {_nl(v['bytes'] / 1e9, 1)} GB" if v.get("bytes") is not None else ""
                lines.append(f"{html.escape(v['name'])}: OK · {minutes} min{size}")
            else:
                error = f" ({html.escape(v['last_error'])})" if v.get("last_error") else ""
                lines.append(f"{html.escape(v['name'])}: failed{error}")
        if history.get("next_due"):
            lines.append(f"Next run {_when(history['next_due'], cfg)}")
        return "\n".join(lines + mirror_lines(store, cfg))
    nas = store.get_cache("nas")
    if nas and nas.get("backup", {}).get("at"):
        state = {"ok": "Succeeded", "fail": "Failed"}.get(nas["backup"]["status"], "Unknown")
        return f"<b>Last backup: {state}</b>\n{_when(nas['backup']['at'], cfg)}"
    return "<b>Backups</b>\nNo backup recorded yet."


def mirror_lines(store: Store, cfg: dict[str, Any]) -> list[str]:
    """The GitHub mirror's last run, for under the backup report."""
    mirror = store.get_cache("github_mirror") or {}
    runs = mirror.get("runs") or []
    if not mirror.get("enabled") or not runs:
        return []
    last = runs[0]
    if last["ok"]:
        state = f"OK · {last['repos']} repos · {_nl(last['bytes'] / 1e9, 1)} GB"
    elif last["failed"]:
        state = f"failed ({last['failed']} of {last['repos']} repos)"
    else:
        state = "failed, see the Backups page"
    return [f"\n<b>GitHub mirror</b>: {state}", _when(last["finished"], cfg)]


def portfolio_text(store: Store, cfg: dict[str, Any]) -> str:
    p = store.get_cache("portfolio")
    if not p:
        return "<b>Portfolio</b>\nNo portfolio data yet."
    move, pct = day_move(p)
    sign = "+" if pct >= 0 else "−"
    lines = [
        f"<b>€ {_nl(p['total_value'])}</b>",
        f"Today {sign}€ {_nl(abs(move))} ({sign}{_nl(abs(pct), 2)}%)",
    ]
    movers = sorted(p.get("holdings", []), key=lambda h: abs(h["day_pct"]), reverse=True)[:3]
    for h in movers:
        sign = "+" if h["day_pct"] >= 0 else "−"
        lines.append(f"{html.escape(h['symbol'])} {sign}{_nl(abs(h['day_pct']), 1)}%")
    if p.get("stale"):
        lines.append("<i>Figures are out of date.</i>")
    return "\n".join(lines)


def help_text() -> str:
    return "<b>Home hub</b>\n" + "\n".join(f"/{c} · {d}" for c, d in COMMANDS.items())


REPLIES = {"status": status_text, "backup": backup_text, "portfolio": portfolio_text}


# --- handling updates -------------------------------------------------------------------


def parse_command(text: str, bot_name: str | None) -> str | None:
    """'/status' or '/status@ThisBot' → 'status'; None for plain text or a
    command addressed to another bot."""
    if not text.startswith("/"):
        return None
    word = text.split()[0][1:]
    name, _, target = word.partition("@")
    if target and bot_name and target.lower() != bot_name.lower():
        return None
    return name.lower()


async def handle_update(
    store: Store, cfg: dict[str, Any], update: dict[str, Any], telegram: Telegram,
    bot_name: str | None,
) -> bool:
    """Answer one update if it is a command from an allowed chat. Returns whether it replied."""
    message = update.get("message") or {}
    chat_id = str((message.get("chat") or {}).get("id", ""))
    allowed = {c["id"]: key for key, c in core.chats(cfg).items() if c["id"]}
    if chat_id not in allowed:
        return False
    command = parse_command(message.get("text") or "", bot_name)
    if command is None:
        return False
    reply = REPLIES.get(command, lambda *_: help_text())(store, cfg)
    sender = (message.get("from") or {}).get("first_name") or "someone"
    now = datetime.now(UTC)
    try:
        await telegram.send(chat_id, reply)
        status, error = "sent", None
    except Exception as exc:  # logged below; the poller carries on
        status, error = "failed", type(exc).__name__
    core.log_entry(
        store, now, source="bot", category="bot", severity="info",
        title=f"/{command} from {sender}", body="", chat=allowed[chat_id],
        status=status, error=error, sent_at=now.isoformat() if status == "sent" else None,
    )
    return True


async def run(store: Store, cfg: dict[str, Any], telegram: Telegram | None = None) -> None:
    """Poll for commands until cancelled. Errors back off and retry."""
    token = ((cfg.get("telegram") or {}).get("token") or "").strip()
    if not token and telegram is None:
        log.info("no bot token: the Telegram bot is off")
        return
    telegram = telegram or Telegram(token)
    bot_name = None
    try:
        me = await telegram.call("getMe", {})
        bot_name = me.get("username")
        await telegram.call("setMyCommands", {"commands": [
            {"command": c, "description": d} for c, d in COMMANDS.items()]})
    except Exception as exc:
        log.warning("bot setup failed: %s", type(exc).__name__)

    backoff = 5
    while True:
        offset = core.get_setting(store, OFFSET_KEY, 0)
        try:
            updates = await telegram.call(
                "getUpdates",
                {"offset": offset, "timeout": POLL_SECONDS, "allowed_updates": ["message"]},
                timeout=POLL_SECONDS + 10,
            )
            backoff = 5
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            # 409 means another poller uses this bot; anything else is transient.
            log.warning("bot poll failed: %s; retrying in %ss", type(exc).__name__, backoff)
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 300)
            continue
        for update in updates or []:
            try:
                await handle_update(store, cfg, update, telegram, bot_name)
            except Exception as exc:
                log.warning("bot update failed: %s", type(exc).__name__)
            core.put_setting(store, OFFSET_KEY, update["update_id"] + 1)
