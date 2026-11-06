"""A week of prices per holding, half-hourly, for the House panel's Stock screen and the
Portfolio page's week card (decided 2026-11-06: one stock's week at a time, a random
holding each turn, in place of the movers heat map).

Ghostfolio keeps only daily closes (five points a week), so the week comes from Yahoo's
chart endpoint, as the indices do:

    GET https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?range=5d&interval=30m
        -> chart.result[0].meta.{currency, regularMarketPrice, chartPreviousClose,
                                 exchangeTimezoneName}
           chart.result[0].timestamp[]             (seconds, UTC)
           chart.result[0].indicators.quote[0].close[]  (null for a half hour without trades)

`chartPreviousClose` is the close before the five days, so the week's change is the
last price against it.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from typing import Any
from urllib.parse import quote

import httpx

from ..store import Store
from .indices import BASE_URL, TIMEOUT_SECONDS
from .models import StockWeek, StockWeeks, WeekPoint

log = logging.getLogger(__name__)

CACHE_KEY = "stock_weeks"
# Ghostfolio prices these from Yahoo too; a holding from another source has no Yahoo symbol.
YAHOO = {"YAHOO", None}


def parse(symbol: str, payload: dict[str, Any]) -> StockWeek | None:
    try:
        result = payload["chart"]["result"][0]
    except (KeyError, IndexError, TypeError):
        return None
    meta = result.get("meta") or {}
    closes = ((result.get("indicators") or {}).get("quote") or [{}])[0].get("close") or []
    points = [WeekPoint(t=datetime.fromtimestamp(t, UTC), price=round(c, 4))
              for t, c in zip(result.get("timestamp") or [], closes, strict=False) if c]
    if len(points) < 2:
        return None
    previous = meta.get("chartPreviousClose")
    return StockWeek(
        symbol=symbol,
        currency=meta.get("currency"),
        price=round(meta.get("regularMarketPrice") or points[-1].price, 4),
        previous_close=round(previous, 4) if previous else None,
        zone=meta.get("exchangeTimezoneName") or "UTC",
        points=points,
    )


def symbols(store: Store) -> list[str]:
    """The holdings Yahoo can price, largest first (as the portfolio lists them)."""
    holdings = (store.get_cache("portfolio") or {}).get("holdings") or []
    return [h["symbol"] for h in holdings
            if h.get("symbol") and h.get("data_source") in YAHOO and h.get("weight_pct", 0) > 0]


async def collect(store: Store, transport: httpx.AsyncBaseTransport | None = None) -> StockWeeks:
    wanted = symbols(store)

    async def one(http: httpx.AsyncClient, symbol: str) -> StockWeek | None:
        try:
            resp = await http.get(BASE_URL + quote(symbol, safe=""),
                                  params={"range": "5d", "interval": "30m"})
            resp.raise_for_status()
            return parse(symbol, resp.json())
        except (httpx.HTTPError, ValueError) as exc:
            log.warning("no week for %s: %s", symbol, type(exc).__name__)
            return None

    async with httpx.AsyncClient(
        transport=transport, timeout=TIMEOUT_SECONDS,
        headers={"User-Agent": "Mozilla/5.0 (compatible; home-hub/1.0)"},
    ) as http:
        weeks = await asyncio.gather(*(one(http, s) for s in wanted))
    found = [w for w in weeks if w]
    if wanted and not found:
        raise RuntimeError("no stock weeks")  # keeps the last good ones, marked stale
    return StockWeeks(as_of=datetime.now(UTC), stocks=found)
