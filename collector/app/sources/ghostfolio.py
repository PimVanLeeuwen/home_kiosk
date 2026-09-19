"""Builds /api/portfolio from Ghostfolio.

Read-only: this project never writes to Ghostfolio.

Endpoints verified against a running 2.x instance (plan.md §6) — several paths
in older documentation are gone, notably `/api/v1/portfolio/performance`, which
is now v2.

    POST /api/v1/auth/anonymous            security token -> bearer JWT
    GET  /api/v1/portfolio/details         summary + holdings
    GET  /api/v2/portfolio/performance     performance + daily chart, per range

Percentages come back as fractions (0.9271 for +92.71%), so everything is
scaled by 100 on the way out.

Ghostfolio has no per-holding daily change — it reports performance since
purchase, and passing `range=1d` changes nothing. `holdings[].day_pct` is
therefore filled in by the price source, not here.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from typing import Any

import httpx

from ..models import AllocationSlice, HistoryPoint, Holding, Portfolio, PortfolioChange

log = logging.getLogger(__name__)

TIMEOUT_SECONDS = 20

# Cash balances come back as ordinary holdings (assetClass LIQUIDITY, symbol
# "EUR") *and* in summary.cash. Counting both double-counts it and renders cash
# as a fake holding row, so these are skipped in the holdings loop.
CASH_ASSET_CLASSES = {"LIQUIDITY"}

# Ghostfolio reports an asset sub-class per holding; these become the
# allocation card's labels. Anything unrecognised falls through to "Other".
SUB_CLASS_LABELS = {
    "STOCK": "Equities",
    "ETF": "ETFs",
    "CRYPTOCURRENCY": "Crypto",
    "BOND": "Bonds",
    "COMMODITY": "Commodities",
}

# Accepted ranges are 1d, wtd, mtd, ytd, 1y, 5y, max — verified against a live
# instance. There is no `1mo`/`3m`; month-to-date is the closest equivalent.
RANGES = {"day": "1d", "month": "mtd", "year": "1y", "all": "max"}

HISTORY_POINTS = 30

# Daily closes requested per symbol for the day-change calculation. A handful
# covers weekends and market holidays, where the latest close may be days old.
HISTORY_LOOKBACK = 6


class GhostfolioError(Exception):
    """Ghostfolio could not be reached or refused the token."""


class Client:
    """Holds the bearer token between refreshes and renews it on a 401."""

    def __init__(self, base_url: str, security_token: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.security_token = security_token
        self._bearer: str | None = None

    async def _authenticate(self, client: httpx.AsyncClient) -> str:
        resp = await client.post(
            f"{self.base_url}/api/v1/auth/anonymous",
            json={"accessToken": self.security_token},
            timeout=TIMEOUT_SECONDS,
        )
        if resp.status_code >= 400:
            raise GhostfolioError(f"auth failed ({resp.status_code})")
        token = resp.json().get("authToken")
        if not token:
            raise GhostfolioError("auth returned no token")
        self._bearer = token
        return token

    async def get(self, client: httpx.AsyncClient, path: str, **params: Any) -> dict:
        for attempt in (1, 2):
            if not self._bearer:
                await self._authenticate(client)
            resp = await client.get(
                f"{self.base_url}{path}",
                params=params or None,
                headers={"Authorization": f"Bearer {self._bearer}"},
                timeout=TIMEOUT_SECONDS,
            )
            if resp.status_code == 401 and attempt == 1:
                self._bearer = None       # expired; re-auth once and retry
                continue
            if resp.status_code >= 400:
                raise GhostfolioError(f"{path} returned {resp.status_code}")
            return resp.json()
        raise GhostfolioError(f"{path} unauthorised after refresh")


def _pct(value: Any) -> float:
    """Ghostfolio reports fractions; the API and the views use percentages."""
    return round((value or 0.0) * 100, 2)


async def _day_changes(
    client: Client, http: httpx.AsyncClient, symbols: list[str]
) -> dict[str, float]:
    """Today's move per symbol, from Ghostfolio's own Yahoo market data.

    Ghostfolio has no per-holding daily change of its own, but it already
    stores daily closes for every held symbol, so the figure can be derived
    without a second data provider.

    This replaces the Twelve Data batch quotes originally planned: its free
    tier is US-only and rejects every European holding with "not available
    with your plan" — which is five of eleven here, including the second,
    third and fourth largest positions. Cross-checked on NVDA, where this
    yields 1.34% against Twelve Data's own 1.33583%.

    `historicalData` ends with *today's* close, so the previous session is the
    second-to-last point.
    """

    async def one(symbol: str) -> tuple[str, float]:
        try:
            data = await client.get(
                http, f"/api/v1/symbol/YAHOO/{symbol}", includeHistoricalData=HISTORY_LOOKBACK
            )
        except GhostfolioError as exc:
            log.warning("no market data for %s: %s", symbol, exc)
            return symbol, 0.0

        price = data.get("marketPrice")
        history = data.get("historicalData") or []
        if not price or len(history) < 2:
            return symbol, 0.0

        previous = history[-2].get("value")
        if not previous:
            return symbol, 0.0
        return symbol, round((price - previous) / previous * 100, 2)

    pairs = await asyncio.gather(*(one(s) for s in symbols))
    return dict(pairs)


def _is_cash(profile: dict) -> bool:
    return (profile.get("assetClass") or "") in CASH_ASSET_CLASSES


def _holdings(details: dict) -> list[Holding]:
    """Real positions only — cash is reported separately in the allocation."""
    out: list[Holding] = []
    for entry in details.get("holdings") or []:
        profile = entry.get("assetProfile") or {}
        symbol = profile.get("symbol")
        if not symbol or _is_cash(profile):
            continue
        out.append(
            Holding(
                symbol=symbol,
                name=profile.get("name") or symbol,
                value=round(entry.get("valueInBaseCurrency") or 0.0, 2),
                # Filled in from live quotes; Ghostfolio cannot supply it.
                day_pct=0.0,
                weight_pct=_pct(entry.get("allocationInPercentage")),
            )
        )
    out.sort(key=lambda h: h.value, reverse=True)
    return out


def _allocation(details: dict) -> list[AllocationSlice]:
    """Group holdings by asset sub-class, plus cash from the summary."""
    totals: dict[str, float] = {}
    for entry in details.get("holdings") or []:
        profile = entry.get("assetProfile") or {}
        if _is_cash(profile):
            continue          # counted once, from summary.cash below
        label = SUB_CLASS_LABELS.get(profile.get("assetSubClass") or "", "Other")
        totals[label] = totals.get(label, 0.0) + (entry.get("valueInBaseCurrency") or 0.0)

    cash = (details.get("summary") or {}).get("cash") or 0.0
    if cash > 0:
        totals["Cash"] = totals.get("Cash", 0.0) + cash

    grand = sum(totals.values())
    if not grand:
        return []

    slices = [
        AllocationSlice(label=label, pct=round(value / grand * 100, 1))
        for label, value in totals.items()
    ]
    slices.sort(key=lambda s: s.pct, reverse=True)
    return slices


def _history(performance: dict) -> list[HistoryPoint]:
    """The last 30 daily points of the full chart.

    Taken from the `max` range rather than a monthly one: the chart is
    downsampled over long spans, but its most recent points are exactly one day
    apart, so the tail is a true 30-day daily series.
    """
    chart = performance.get("chart") or []
    points = [
        HistoryPoint(d=row["date"], v=round(row.get("netWorth") or row.get("value") or 0.0, 2))
        for row in chart
        if row.get("date")
    ]
    return points[-HISTORY_POINTS:]


async def collect(cfg: dict[str, Any], currency: str) -> Portfolio:
    gf_cfg = cfg["ghostfolio"]
    token = gf_cfg.get("security_token") or ""
    if not token:
        raise GhostfolioError("GHOSTFOLIO_TOKEN is not set")

    client = Client(gf_cfg["base_url"], token)

    async with httpx.AsyncClient() as http:
        details = await client.get(http, "/api/v1/portfolio/details")
        # One request per range; they are independent so run them together.
        results = await asyncio.gather(
            *(
                client.get(http, "/api/v2/portfolio/performance", range=rng)
                for rng in RANGES.values()
            )
        )

    by_range = dict(zip(RANGES, results, strict=True))
    day = (by_range["day"].get("performance") or {})
    summary = details.get("summary") or {}

    holdings = _holdings(details)
    async with httpx.AsyncClient() as http:
        changes = await _day_changes(client, http, [h.symbol for h in holdings])
    for holding in holdings:
        holding.day_pct = changes.get(holding.symbol, 0.0)

    return Portfolio(
        as_of=datetime.now(UTC),
        stale=False,
        currency=currency,
        total_value=round(summary.get("currentValueInBaseCurrency") or 0.0, 2),
        change=PortfolioChange(
            day_abs=round(day.get("netPerformanceWithCurrencyEffect") or 0.0, 2),
            day_pct=_pct(day.get("netPerformancePercentageWithCurrencyEffect")),
            month_pct=_pct(
                (by_range["month"].get("performance") or {})
                .get("netPerformancePercentageWithCurrencyEffect")
            ),
            year_pct=_pct(
                (by_range["year"].get("performance") or {})
                .get("netPerformancePercentageWithCurrencyEffect")
            ),
            all_pct=_pct(
                (by_range["all"].get("performance") or {})
                .get("netPerformancePercentageWithCurrencyEffect")
            ),
        ),
        history=_history(by_range["all"]),
        holdings=holdings,
        allocation=_allocation(details),
    )
