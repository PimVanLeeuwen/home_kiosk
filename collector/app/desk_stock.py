"""The House panel's Stock screen (decided 2026-11-06, in place of the movers heat map):
one holding's last five trading days as a large line, a different holding each time the
screen comes round. The hub sends every holding's week and the panel draws one at random
(equal chances, never the same twice in a row), so a stock never changes while shown.

Percentages and the share price only (the desk is visible to visitors, 2026-10-23): no
amounts or quantities leave the hub. The line's points are scaled to 0..1000 over the
week's low and high and the previous close (`base`, on the same scale), so the dashed line
the week's change is measured from always fits in the chart.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .portfolio import weeks
from .store import Store

MAX_STOCKS = 12
MAX_POINTS = 72
NAME_CHARS = 40
# The panel fonts stop at Latin-1, so no euro sign.
CURRENCY = {"USD": "${:,.2f}", "GBP": "£{:,.2f}", "GBp": "{:,.1f}p", "EUR": "{:,.2f} EUR"}


def pct(value: float, digits: int = 2) -> str:
    """"+2.54%", "-0.27%": a plain hyphen, as the panel fonts stop at Latin-1."""
    if round(value, digits) == 0:
        return f"{0:.{digits}f}%"
    return f"{'+' if value > 0 else '-'}{abs(value):.{digits}f}%"


def price(value: float, currency: str | None) -> str:
    form = CURRENCY.get(currency or "")
    if form:
        return form.format(value)
    return f"{value:,.2f} {currency}" if currency else f"{value:,.2f}"


def ticker(symbol: str) -> str:
    """Without the exchange: "XDWT.L" is "XDWT"."""
    return symbol.split(".")[0] if "." in symbol else symbol


def _zone(name: str) -> ZoneInfo:
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError):
        return ZoneInfo("UTC")


def _thin(count: int) -> list[int]:
    """Which of `count` points to keep: at most MAX_POINTS, evenly, first and last too."""
    if count <= MAX_POINTS:
        return list(range(count))
    step = (count - 1) / (MAX_POINTS - 1)
    return [round(i * step) for i in range(MAX_POINTS)]


def week(stock: dict[str, Any], holding: dict[str, Any]) -> dict[str, Any] | None:
    """One stock's week for the panel; None without a line to draw."""
    raw = stock.get("points") or []
    if len(raw) < 2:
        return None
    zone = _zone(stock.get("zone") or "UTC")
    kept = _thin(len(raw))
    prices = [raw[i]["price"] for i in kept]
    times = [datetime.fromisoformat(raw[i]["t"]).astimezone(zone) for i in kept]
    base_price = stock.get("previous_close") or prices[0]
    low, high = min(prices), max(prices)
    bottom, top = min(low, base_price), max(high, base_price)
    span = top - bottom or 1.0
    days, seen = [], None
    for i, t in enumerate(times):
        if t.date() != seen:
            seen = t.date()
            days.append({"at": i, "label": t.strftime("%a")})
    last = stock.get("price") or prices[-1]
    change = (last - base_price) / base_price * 100 if base_price else 0.0
    today, gain = holding.get("day_pct"), holding.get("gain_pct")
    currency = stock.get("currency")
    return {
        "ticker": ticker(stock["symbol"]),
        "name": (holding.get("name") or "")[:NAME_CHARS],
        "price": price(last, currency),
        "week": pct(change), "up": change >= 0,
        "today": f"TODAY {pct(today)}" if today is not None else "",
        "today_up": (today or 0) >= 0,
        "gain": f"YOURS {pct(gain, 1)}" if gain is not None else "",
        "gain_up": (gain or 0) >= 0,
        "points": [round((p - bottom) / span * 1000) for p in prices],
        "base": round((base_price - bottom) / span * 1000),
        "days": days,
        "high": price(high, currency), "high_at": prices.index(high),
        "low": price(low, currency), "low_at": prices.index(low),
    }


def stock_screen(store: Store, zone: ZoneInfo, now: datetime) -> dict[str, Any]:
    data = store.get_cache(weeks.CACHE_KEY) or {}
    holdings = {h["symbol"]: h for h in (store.get_cache("portfolio") or {}).get("holdings") or []
                if h.get("symbol")}
    stocks = []
    for stock in data.get("stocks") or []:
        if stock.get("symbol") not in holdings:
            continue  # sold since the week was fetched
        found = week(stock, holdings[stock["symbol"]])
        if found:
            stocks.append(found)
    if not stocks:
        return {"kind": "stock", "stale": False, "present": False}
    return {
        "kind": "stock",
        "stale": bool(data.get("stale")),
        "present": True,
        "title": "THIS WEEK",
        "stocks": stocks[:MAX_STOCKS],
    }
