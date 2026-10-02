"""The portfolio report to the Portfolio chat, replacing stock-bot.

Same shape as stock-bot's: the value and today's move, one line per holding
with its move in % and euros, then the index line. It runs on weekdays at the
times in `portfolio.report.schedule` and is built from the hub's cached data,
like the bot's replies.

The total move is the sum of the holdings' moves (moves.py), so the lines
always add up. In the morning that is the previous session.
"""

from __future__ import annotations

import html
import logging
import re
from datetime import UTC, datetime, timedelta
from typing import Any

from apscheduler.triggers.cron import CronTrigger

from ..alerts import core
from ..store import Store
from .moves import day_move

log = logging.getLogger(__name__)

# APScheduler counts crontab weekdays from Monday = 0, so names, never numbers.
DEFAULT_SCHEDULE = "30 8,18 * * mon-fri"
# Older figures than this get a note: the Ghostfolio refresh runs every 15 minutes.
FRESH = timedelta(minutes=45)
RULE = "━━━━━━━━━━━━━━"


def settings(cfg: dict[str, Any]) -> dict[str, Any]:
    report = (cfg.get("portfolio") or {}).get("report") or {}
    return {"enabled": report.get("enabled", True),
            "schedule": report.get("schedule") or DEFAULT_SCHEDULE}


def trigger(cfg: dict[str, Any]) -> CronTrigger:
    return CronTrigger.from_crontab(settings(cfg)["schedule"],
                                    timezone=cfg.get("timezone", "UTC"))


def _nl(n: float, digits: int = 2) -> str:
    """Dutch number formatting, like the rest of the hub: 12.345,67."""
    text = f"{n:,.{digits}f}"
    return text.replace(",", "§").replace(".", ",").replace("§", ".")


def _money(n: float, signed: bool = False) -> str:
    sign = ("+" if n >= 0 else "−") if signed else ("−" if n < 0 else "")
    return f"{sign}€ {_nl(abs(n), 0 if abs(n) >= 1000 else 2)}"


def _pct(n: float) -> str:
    return f"{'+' if n >= 0 else '−'}{_nl(abs(n))}%"


def _dot(n: float) -> str:
    return "🟢" if n > 0 else "🔴" if n < 0 else "⚪"


def build(portfolio: dict[str, Any], indices: dict[str, Any] | None, cfg: dict[str, Any],
          now: datetime) -> tuple[str, str]:
    """The report as (title, Telegram HTML)."""
    local = core.local(now, cfg)
    title = "Morning report" if local.hour < 12 else "Evening report"
    holdings = portfolio.get("holdings") or []
    total = portfolio["total_value"]
    change, pct = day_move(portfolio)

    lines = [
        f"📈 <b>{title}</b> · {local.strftime('%a %d %b, %H:%M')}",
        "",
        f"💼 <b>{_money(total)}</b>",
        f"{_dot(change)} <b>{_money(change, signed=True)}</b> ({_pct(pct)}) today",
        RULE,
    ]
    for h in sorted(holdings, key=lambda h: h.get("day_pct") or 0.0, reverse=True):
        day = h.get("day_pct") or 0.0
        lines.append(f"{_dot(day)} <b>{html.escape(h['symbol'])}</b>  {_pct(day)}  "
                     f"({_money(h.get('day_abs') or 0.0, signed=True)})")
    quotes = (indices or {}).get("indices") or []
    if quotes:
        lines.append(RULE)
        lines.append("  ".join(f"{_dot(q['day_pct'])} {html.escape(q['label'])} "
                               f"{_pct(q['day_pct'])}" for q in quotes))
    as_of = datetime.fromisoformat(portfolio["as_of"])
    if portfolio.get("stale") or now - as_of > FRESH:
        lines.append(f"\n<i>Figures from {core.local(as_of, cfg).strftime('%a %H:%M')}; "
                     "Ghostfolio is not answering.</i>")
    return title, "\n".join(lines)


def plain(text: str) -> str:
    """The HTML report as text, for the message log on the Alerts page."""
    return html.unescape(re.sub(r"<[^>]+>", "", text))


async def send(store: Store, cfg: dict[str, Any], now: datetime | None = None,
               telegram: Any = None) -> None:
    """The scheduled job. Without portfolio data it logs a failed message instead."""
    now = now or datetime.now(UTC)
    portfolio = store.get_cache("portfolio")
    if not portfolio:
        core.log_entry(store, now, source="hub", category="portfolio", severity="warning",
                       title="Portfolio report skipped", body="",
                       chat=core.routing(store).get("portfolio", "portfolio"),
                       status="failed", error="No portfolio data yet")
        return
    title, text = build(portfolio, store.get_cache("indices"), cfg, now)
    body = plain(text).split("\n", 2)[-1].strip()  # the title line is logged separately
    await core.notify(store, cfg, source="hub", category="portfolio", severity="info",
                      title=title, body=body, formatted=text, now=now, telegram=telegram)
