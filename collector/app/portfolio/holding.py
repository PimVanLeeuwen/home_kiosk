"""One holding in detail: its price history against your average price, and its
transactions. Fetched from Ghostfolio when opened and kept for a few minutes.

Contract checked against the Ghostfolio 3.76.0 source:

    GET /api/v1/portfolio/holding/{dataSource}/{symbol}
        -> quantity, averagePrice, marketPrice(Min|Max), value, performance,
           historicalData[{date, marketPrice}]  (its averagePrice per day is not
           split-adjusted, so the page draws today's average instead)
    GET /api/v1/activities?dataSource=&symbol=&sortColumn=date&sortDirection=desc
        -> {activities: [{date, type, quantity, unitPrice, fee, currency, valueInBaseCurrency}]}
"""

from __future__ import annotations

import re
import time
from typing import Any
from urllib.parse import quote

import httpx

from ..sources.ghostfolio import Client, GhostfolioError, _pct, _round
from .models import HoldingActivity, HoldingDetail, PricePoint

CACHE_SECONDS = 300
MAX_POINTS = 400
DATA_SOURCE = re.compile(r"^[A-Z_]{2,20}$")
SYMBOL = re.compile(r"^[A-Za-z0-9.^=_-]{1,30}$")

_cache: dict[tuple[str, str], tuple[float, HoldingDetail]] = {}
_clients: dict[tuple[str, str], Client] = {}


class NotFound(Exception):
    pass


def _client(cfg: dict[str, Any]) -> Client:
    gf = cfg.get("ghostfolio") or {}
    token = gf.get("security_token") or ""
    if not token:
        raise GhostfolioError("GHOSTFOLIO_TOKEN is not set")
    key = (gf["base_url"], token)
    if key not in _clients:
        _clients[key] = Client(gf["base_url"], token)
    return _clients[key]


def _thin(points: list[PricePoint]) -> list[PricePoint]:
    """At most MAX_POINTS, always keeping the latest."""
    if len(points) <= MAX_POINTS:
        return points
    step = len(points) / MAX_POINTS
    picked = [points[int(i * step)] for i in range(MAX_POINTS - 1)]
    return [*picked, points[-1]]


def _despike(points: list[PricePoint]) -> list[PricePoint]:
    """Drop lone points far off both neighbours. Ghostfolio's first point is the
    price as booked, which after a split (NVDA, 10 for 1) is ten times the
    adjusted prices around it."""

    def off(a: float, b: float) -> bool:
        return a > 2 * b or a < b / 2

    kept = []
    for i, p in enumerate(points):
        neighbours = [points[j].price for j in (i - 1, i + 1) if 0 <= j < len(points)]
        if neighbours and all(off(p.price, n) for n in neighbours) and len(points) > 2:
            continue
        kept.append(p)
    return kept


def parse(data_source: str, symbol: str, holding: dict, activities: dict) -> HoldingDetail:
    profile = holding.get("assetProfile") or {}
    history = [
        PricePoint(d=row["date"], price=round(row["marketPrice"], 4))
        for row in holding.get("historicalData") or []
        if row.get("date") and row.get("marketPrice")
    ]
    gain_pct = holding.get("netPerformancePercentWithCurrencyEffect")
    return HoldingDetail(
        symbol=symbol,
        data_source=data_source,
        name=profile.get("name") or symbol,
        isin=profile.get("isin") or None,
        currency=profile.get("currency"),
        quantity=holding.get("quantity") or 0,
        average_price=round(holding.get("averagePrice") or 0, 4),
        price=round(holding.get("marketPrice") or 0, 4),
        price_min=_round(holding.get("marketPriceMin"), 4),
        price_max=_round(holding.get("marketPriceMax"), 4),
        value=round(holding.get("value") or 0, 2),
        invested=_round(holding.get("investmentInBaseCurrencyWithCurrencyEffect")),
        gain_abs=_round(holding.get("netPerformanceWithCurrencyEffect")),
        gain_pct=None if gain_pct is None else _pct(gain_pct),
        dividends=_round(holding.get("dividendInBaseCurrency")),
        fees=_round(holding.get("feeInBaseCurrency")),
        first_activity=holding.get("dateOfFirstActivity"),
        history=_thin(_despike(history)),
        activities=[
            HoldingActivity(
                date=a["date"], type=a.get("type") or "", quantity=a.get("quantity") or 0,
                unit_price=a.get("unitPrice") or 0, fee=a.get("fee") or 0,
                currency=a.get("currency") or profile.get("currency") or "",
                value=_round(a.get("valueInBaseCurrency")),
            )
            for a in activities.get("activities") or []
            if a.get("date")
        ],
    )


async def detail(cfg: dict[str, Any], data_source: str, symbol: str,
                 transport: httpx.AsyncBaseTransport | None = None) -> HoldingDetail:
    if not DATA_SOURCE.match(data_source) or not SYMBOL.match(symbol):
        raise NotFound
    key = (data_source, symbol)
    hit = _cache.get(key)
    if hit and time.monotonic() - hit[0] < CACHE_SECONDS:
        return hit[1]

    client = _client(cfg)
    async with httpx.AsyncClient(transport=transport) as http:
        try:
            holding = await client.get(
                http, f"/api/v1/portfolio/holding/{data_source}/{quote(symbol, safe='')}")
        except GhostfolioError as exc:
            if "404" in str(exc):
                raise NotFound from exc
            raise
        activities = await client.get(
            http, "/api/v1/activities", dataSource=data_source, symbol=symbol,
            sortColumn="date", sortDirection="desc", take=200)
    result = parse(data_source, symbol, holding, activities)
    _cache[key] = (time.monotonic(), result)
    return result
