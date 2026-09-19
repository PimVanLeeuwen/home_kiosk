"""Builds /api/spotlight — one holding featured at a time.

Selection is a **random holding, re-picked on each refresh** rather than the
biggest mover: the largest mover tends to be the same name for days at a stretch,
which makes the view predictable. The previous pick is remembered so the same
holding is not featured twice in a row.

Prices and history come from Ghostfolio's own Yahoo market data, not Twelve
Data, whose free tier cannot price European holdings at all (see
`ghostfolio._day_changes`).

Two fields the design allows for are simply not available from this source and
are omitted rather than faked:

  * `day_range` — Ghostfolio stores daily closes, not intraday high/low.
  * `next_earnings` — no earnings calendar.
"""

from __future__ import annotations

import logging
import random
from datetime import UTC, datetime
from typing import Any

import httpx

from ..models import HistoryPoint, Position, Range, Spotlight
from ..store import Store
from .ghostfolio import (
    Client,
    GhostfolioError,
    _is_cash,
    _pct,
)

log = logging.getLogger(__name__)

LAST_PICK_KEY = "spotlight_last"

# A year of daily closes; every 7th gives the ~52 weekly points the chart wants.
HISTORY_DAYS = 365
WEEKLY_STRIDE = 7

# Ghostfolio exposes no exchange name, so it is derived from the ticker suffix.
EXCHANGE_BY_SUFFIX = {
    "AS": "Euronext Amsterdam",
    "DE": "XETRA",
    "L": "London Stock Exchange",
    "PA": "Euronext Paris",
    "BR": "Euronext Brussels",
    "MI": "Borsa Italiana",
    "SW": "SIX Swiss Exchange",
}


def _exchange(symbol: str, currency: str) -> str:
    if "." in symbol:
        return EXCHANGE_BY_SUFFIX.get(symbol.rsplit(".", 1)[1].upper(), "")
    # US tickers carry no suffix; the currency is the only hint available.
    return "NASDAQ / NYSE" if currency == "USD" else ""


def _held_since(value: Any) -> str:
    """dateOfFirstActivity -> "YYYY-MM", which the view renders as "Mar 2023"."""
    text = str(value or "")
    return text[:7] if len(text) >= 7 else ""


def _choose(candidates: list[dict], store: Store) -> dict:
    """Random pick, avoiding an immediate repeat."""
    previous = (store.get_cache(LAST_PICK_KEY) or {}).get("symbol")
    pool = [c for c in candidates if c["assetProfile"]["symbol"] != previous]
    chosen = random.choice(pool or candidates)
    store.put_cache(LAST_PICK_KEY, {"symbol": chosen["assetProfile"]["symbol"]})
    return chosen


async def collect(cfg: dict[str, Any], store: Store) -> Spotlight:
    gf_cfg = cfg["ghostfolio"]
    token = gf_cfg.get("security_token") or ""
    if not token:
        raise GhostfolioError("GHOSTFOLIO_TOKEN is not set")

    client = Client(gf_cfg["base_url"], token)

    async with httpx.AsyncClient() as http:
        details = await client.get(http, "/api/v1/portfolio/details")

        holdings = [
            h
            for h in (details.get("holdings") or [])
            if h.get("assetProfile", {}).get("symbol") and not _is_cash(h["assetProfile"])
        ]
        if not holdings:
            raise GhostfolioError("no holdings to feature")

        entry = _choose(holdings, store)
        profile = entry["assetProfile"]
        symbol = profile["symbol"]

        market = await client.get(
            http, f"/api/v1/symbol/YAHOO/{symbol}", includeHistoricalData=HISTORY_DAYS
        )

    daily = [p for p in (market.get("historicalData") or []) if p.get("value")]
    price = market.get("marketPrice") or entry.get("marketPrice") or 0.0

    # Weekly points for the 52-week chart, always keeping the most recent close.
    weekly = daily[::WEEKLY_STRIDE]
    if daily and weekly[-1] is not daily[-1]:
        weekly.append(daily[-1])
    history = [HistoryPoint(d=p["date"][:10], v=round(p["value"], 2)) for p in weekly]

    values = [p["value"] for p in daily] or [price]
    previous_close = daily[-2]["value"] if len(daily) >= 2 else price
    day_abs = round(price - previous_close, 2)
    day_pct = round((day_abs / previous_close * 100) if previous_close else 0.0, 2)

    quantity = entry.get("quantity") or 0.0
    invested = entry.get("investment") or 0.0
    value_base = entry.get("valueInBaseCurrency") or 0.0

    # Ghostfolio mixes currencies: `marketPrice` is in the asset's own currency,
    # while `investment`, `valueInBaseCurrency` and the performance figures are
    # in the portfolio's base currency. Showing both under one label turns a
    # EUR amount into a dollar one. Everything here is expressed in the asset's
    # currency, derived from the two prices rather than an FX lookup.
    price_base = (value_base / quantity) if quantity else 0.0
    fx = (price / price_base) if price_base else 1.0

    return Spotlight(
        as_of=datetime.now(UTC),
        stale=False,
        symbol=symbol,
        name=profile.get("name") or symbol,
        exchange=_exchange(symbol, profile.get("currency") or ""),
        price=round(price, 2),
        currency=profile.get("currency") or cfg.get("currency", "EUR"),
        day_abs=day_abs,
        day_pct=day_pct,
        history=history,
        range_52w=Range(low=round(min(values), 2), high=round(max(values), 2)),
        position=Position(
            shares=quantity,
            avg_cost=round(invested * fx / quantity, 2) if quantity else 0.0,
            invested=round(invested * fx, 2),
            value=round(value_base * fx, 2),
            unrealised_abs=round((entry.get("netPerformanceWithCurrencyEffect") or 0.0) * fx, 2),
            unrealised_pct=_pct(entry.get("netPerformancePercentWithCurrencyEffect")),
            weight_pct=_pct(entry.get("allocationInPercentage")),
            held_since=_held_since(entry.get("dateOfFirstActivity")),
        ),
    )
