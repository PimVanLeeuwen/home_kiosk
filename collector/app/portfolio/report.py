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

from ..alerts import core, templates
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
          now: datetime, store: Store | None = None) -> tuple[str, str]:
    """The report as (title, Telegram HTML), worded by the saved templates."""
    local = core.local(now, cfg)
    title = "Morning report" if local.hour < 12 else "Evening report"
    holdings = portfolio.get("holdings") or []
    change, pct = day_move(portfolio)
    as_of = datetime.fromisoformat(portfolio["as_of"])
    stale = portfolio.get("stale") or now - as_of > FRESH
    values = {
        "title": title,
        "when": local.strftime("%a %d %b, %H:%M"),
        "total": _money(portfolio["total_value"]),
        "dot": _dot(change),
        "change": _money(change, signed=True),
        "change_pct": _pct(pct),
        "holdings": [
            {"dot": _dot(h.get("day_pct") or 0.0), "symbol": h["symbol"],
             "pct": _pct(h.get("day_pct") or 0.0),
             "change": _money(h.get("day_abs") or 0.0, signed=True)}
            for h in sorted(holdings, key=lambda h: h.get("day_pct") or 0.0, reverse=True)
        ],
        "indices": [
            {"dot": _dot(q["day_pct"]), "label": q["label"], "pct": _pct(q["day_pct"])}
            for q in (indices or {}).get("indices") or []
        ],
        "stale_note": [{"as_of": core.local(as_of, cfg).strftime("%a %H:%M")}] if stale else [],
    }
    return title, templates.render(store, "portfolio_report", values)


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
    title, text = build(portfolio, store.get_cache("indices"), cfg, now, store)
    body = plain(text).split("\n", 2)[-1].strip()  # the title line is logged separately
    await core.notify(store, cfg, source="hub", category="portfolio", severity="info",
                      title=title, body=body, formatted=text, now=now, telegram=telegram)
