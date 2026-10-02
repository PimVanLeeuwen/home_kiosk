"""Market indices for the Portfolio page and the daily report.

Ghostfolio only keeps prices for symbols you hold, so the indices come straight
from Yahoo's chart endpoint, the same source Ghostfolio and stock-bot use:

    GET https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?range=5d&interval=1d
        -> chart.result[0].meta.{regularMarketPrice, currency, regularMarketTime}
           chart.result[0].indicators.quote[0].close  (daily, today's last)

The day's move is the last close against the one before, as in ghostfolio.py.
Before the market opens that is the previous session's move, which is what a
morning report should show.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from typing import Any
from urllib.parse import quote

import httpx

from .models import IndexQuote, Indices

log = logging.getLogger(__name__)

BASE_URL = "https://query1.finance.yahoo.com/v8/finance/chart/"
TIMEOUT_SECONDS = 15
DEFAULT_INDICES = ["^GSPC", "^NDX", "^AEX"]
LABELS = {
    "^GSPC": "S&P 500",
    "^NDX": "Nasdaq 100",
    "^IXIC": "Nasdaq",
    "^DJI": "Dow Jones",
    "^AEX": "AEX",
    "^STOXX50E": "Euro Stoxx 50",
    "^FTSE": "FTSE 100",
}


def parse(symbol: str, payload: dict[str, Any]) -> IndexQuote | None:
    try:
        result = payload["chart"]["result"][0]
    except (KeyError, IndexError, TypeError):
        return None
    meta = result.get("meta") or {}
    quotes = (result.get("indicators") or {}).get("quote") or [{}]
    closes = [c for c in quotes[0].get("close") or [] if c]
    price = meta.get("regularMarketPrice") or (closes[-1] if closes else None)
    if not price or len(closes) < 2:
        return None
    previous = closes[-2]
    stamp = meta.get("regularMarketTime")
    return IndexQuote(
        symbol=symbol,
        label=LABELS.get(symbol, symbol.lstrip("^")),
        currency=meta.get("currency"),
        price=round(price, 2),
        day_pct=round((closes[-1] - previous) / previous * 100, 2),
        at=datetime.fromtimestamp(stamp, UTC) if stamp else None,
    )


async def collect(cfg: dict[str, Any],
                  transport: httpx.AsyncBaseTransport | None = None) -> Indices:
    symbols = (cfg.get("portfolio") or {}).get("indices") or DEFAULT_INDICES

    async def one(http: httpx.AsyncClient, symbol: str) -> IndexQuote | None:
        try:
            resp = await http.get(BASE_URL + quote(symbol, safe=""),
                                  params={"range": "5d", "interval": "1d"})
            resp.raise_for_status()
            return parse(symbol, resp.json())
        except (httpx.HTTPError, ValueError) as exc:
            log.warning("no quote for %s: %s", symbol, type(exc).__name__)
            return None

    async with httpx.AsyncClient(
        transport=transport, timeout=TIMEOUT_SECONDS,
        # Yahoo turns away requests without a browser-like agent.
        headers={"User-Agent": "Mozilla/5.0 (compatible; home-hub/1.0)"},
    ) as http:
        quotes = await asyncio.gather(*(one(http, s) for s in symbols))
    found = [q for q in quotes if q]
    if symbols and not found:
        raise RuntimeError("no index quotes")  # keeps the last good ones, marked stale
    return Indices(as_of=datetime.now(UTC), indices=found)
