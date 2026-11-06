from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import httpx
import pytest

from app import desk_stock
from app.portfolio import weeks

ZONE = ZoneInfo("Europe/Amsterdam")
NOW = datetime(2026, 11, 6, 12, 0, tzinfo=UTC)
# Friday 30 October 13:30 and 14:00 UTC, Monday 2 November 14:30 and 15:00 UTC (New York's
# open, before and after its clocks went back).
STAMPS = [1793367000, 1793368800, 1793629800, 1793631600]


def chart(closes, previous=100.0, currency="USD", zone="America/New_York", price=None):
    return {"chart": {"result": [{
        "meta": {"currency": currency, "regularMarketPrice": price or closes[-1],
                 "chartPreviousClose": previous, "exchangeTimezoneName": zone},
        "timestamp": STAMPS[:len(closes)],
        "indicators": {"quote": [{"close": closes}]}}]}}


def holding(symbol, name="", day=None, gain=None, source="YAHOO", weight=10.0):
    return {"symbol": symbol, "name": name or symbol, "data_source": source,
            "weight_pct": weight, "day_pct": day, "gain_pct": gain}


def put_portfolio(store, holdings):
    store.put_cache("portfolio", {"as_of": NOW.isoformat(), "stale": False, "holdings": holdings})


# --- collecting ------------------------------------------------------------------------------


def test_collect_asks_yahoo_for_the_holdings_it_prices(store):
    put_portfolio(store, [holding("NVDA"), holding("ASML.AS"), holding("GOLD", source="MANUAL")])
    asked = []

    def yahoo(request):
        asked.append((request.url.path.rsplit("/", 1)[-1], dict(request.url.params)))
        if "ASML" in request.url.path:
            return httpx.Response(500)
        return httpx.Response(200, json=chart([101.0, None, 104.0]))

    result = asyncio.run(weeks.collect(store, httpx.MockTransport(yahoo)))
    assert asked[0] == ("NVDA", {"range": "5d", "interval": "30m"})
    assert sorted(a[0] for a in asked) == ["ASML.AS", "NVDA"]  # GOLD has no Yahoo symbol
    [nvda] = result.stocks  # ASML failed and is left out
    # A half hour without trades is left out.
    assert [p.price for p in nvda.points] == [101.0, 104.0]
    assert (nvda.previous_close, nvda.zone, nvda.currency) == (100.0, "America/New_York", "USD")


def test_collect_fails_when_nothing_answers(store):
    put_portfolio(store, [holding("NVDA")])
    with pytest.raises(RuntimeError):
        asyncio.run(weeks.collect(store, httpx.MockTransport(lambda r: httpx.Response(500))))


def test_collect_without_holdings_is_empty(store):
    assert asyncio.run(weeks.collect(store, httpx.MockTransport(lambda r: None))).stocks == []


def test_parse_needs_two_prices():
    assert weeks.parse("X", chart([1.0])) is None
    assert weeks.parse("X", {"chart": {"result": None}}) is None


# --- the panel's screen ----------------------------------------------------------------------


def screen(store, closes=(101.0, 99.0, 103.0, 110.0), holdings=None, **kw):
    put_portfolio(store, holdings or [holding("NVDA", "NVIDIA Corporation", day=1.34, gain=212.44)])
    week = weeks.parse("NVDA", chart(list(closes), **kw))
    store.put_cache(weeks.CACHE_KEY, {"as_of": NOW.isoformat(), "stale": False,
                                      "stocks": [week.model_dump(mode="json")]})
    return desk_stock.stock_screen(store, ZONE, NOW)


def test_a_week_scaled_with_its_days_and_extremes(store):
    s = screen(store)
    assert (s["kind"], s["present"], s["title"]) == ("stock", True, "THIS WEEK")
    [nvda] = s["stocks"]
    assert (nvda["ticker"], nvda["name"], nvda["price"]) == (
        "NVDA", "NVIDIA Corporation", "$110.00")
    # The week is measured from the close before it: 100 to 110.
    assert (nvda["week"], nvda["up"]) == ("+10.00%", True)
    assert (nvda["today"], nvda["gain"]) == ("TODAY +1.34%", "YOURS +212.4%")
    assert nvda["points"] == [182, 0, 364, 1000]
    assert nvda["base"] == 91  # 100 between the low 99 and the high 110
    # Trading days in the exchange's own zone.
    assert nvda["days"] == [{"at": 0, "label": "Fri"}, {"at": 2, "label": "Mon"}]
    assert (nvda["high"], nvda["high_at"], nvda["low"], nvda["low_at"]) == (
        "$110.00", 3, "$99.00", 1)


def test_a_falling_week_and_other_currencies(store):
    [s] = screen(store, closes=(14.0, 13.0), previous=15.0, currency="GBp",
                 holdings=[holding("NVDA", day=-0.5)])["stocks"]
    assert (s["week"], s["up"], s["price"], s["today_up"], s["gain"]) == (
        "-13.33%", False, "13.0p", False, "")
    # The previous close above the week: the scale reaches up to it.
    assert (s["points"], s["base"]) == ([500, 0], 1000)
    assert desk_stock.price(41.2, "EUR") == "41.20 EUR"  # the panel fonts have no euro sign
    assert desk_stock.price(1234.5, "GBP") == "£1,234.50"
    assert desk_stock.price(9.5, "CHF") == "9.50 CHF"


def test_long_weeks_are_thinned_keeping_the_ends():
    kept = desk_stock._thin(200)
    assert len(kept) == desk_stock.MAX_POINTS and (kept[0], kept[-1]) == (0, 199)
    assert desk_stock._thin(5) == [0, 1, 2, 3, 4]


def test_a_sold_holding_or_no_weeks_shows_nothing(store):
    assert screen(store, holdings=[holding("ASML.AS")]) == {
        "kind": "stock", "stale": False, "present": False}
    store.put_cache(weeks.CACHE_KEY, {"as_of": NOW.isoformat(), "stale": True, "stocks": []})
    assert desk_stock.stock_screen(store, ZONE, NOW)["present"] is False
