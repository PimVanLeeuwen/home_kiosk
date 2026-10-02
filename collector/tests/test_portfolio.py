from __future__ import annotations

import asyncio
from urllib.parse import unquote

import httpx
import pytest
from fastapi.testclient import TestClient

from app import main
from app.portfolio import holding, indices
from app.sources import ghostfolio

CFG = {"ghostfolio": {"base_url": "http://gf.lan:3333", "security_token": "token"},
       "portfolio": {"indices": ["^GSPC", "^AEX"]}}

DETAILS = {
    "summary": {"currentValueInBaseCurrency": 12000.0, "totalInvestment": 9000.0,
                "totalInvestmentValueWithCurrencyEffect": 9100.0, "cash": 500.0,
                "dividendInBaseCurrency": 42.5},
    "holdings": [
        {"assetProfile": {"symbol": "ASML.AS", "name": "ASML Holding", "dataSource": "YAHOO",
                          "isin": "NL0010273215", "currency": "EUR", "assetClass": "EQUITY",
                          "assetSubClass": "STOCK"},
         "valueInBaseCurrency": 8000.0, "allocationInPercentage": 0.6667, "quantity": 10,
         "marketPrice": 800.0, "investment": 6000.0, "netPerformanceWithCurrencyEffect": 2000.0,
         "netPerformancePercentWithCurrencyEffect": 0.3333},
        {"assetProfile": {"symbol": "NVDA", "name": "NVIDIA", "dataSource": "YAHOO",
                          "currency": "USD", "assetClass": "EQUITY", "assetSubClass": "STOCK"},
         "valueInBaseCurrency": 3500.0, "allocationInPercentage": 0.2917, "quantity": 20,
         "marketPrice": 190.0, "investment": 3000.0, "netPerformanceWithCurrencyEffect": 500.0,
         "netPerformancePercentWithCurrencyEffect": 0.1667},
        {"assetProfile": {"symbol": "EUR", "assetClass": "LIQUIDITY"},
         "valueInBaseCurrency": 500.0},
    ],
}


def performance(rng: str) -> dict:
    chart = [{"date": f"2026-09-{d:02d}", "netWorth": 11000 + d * 10,
              "totalInvestmentValueWithCurrencyEffect": 9100} for d in range(1, 31)]
    if rng == "max":
        chart = [{"date": "2024-01-01", "netWorth": 1000, "totalInvestment": 1000}] + chart
    return {"performance": {"netPerformanceWithCurrencyEffect": 2500.0 if rng == "max" else 50.0,
                            "netPerformancePercentageWithCurrencyEffect": 0.004},
            "chart": chart}


def symbol(sym: str) -> dict:
    prices = {"ASML.AS": (800.0, 790.0), "NVDA": (190.0, 200.0)}[sym]
    return {"marketPrice": prices[0],
            "historicalData": [{"value": prices[1]}, {"value": prices[0]}]}


HOLDING = {
    "assetProfile": {"symbol": "ASML.AS", "name": "ASML Holding", "isin": "NL0010273215",
                     "currency": "EUR"},
    "quantity": 10, "averagePrice": 600.0, "marketPrice": 800.0, "marketPriceMin": 550.0,
    "marketPriceMax": 900.0, "value": 8000.0, "investmentInBaseCurrencyWithCurrencyEffect": 6000,
    "netPerformanceWithCurrencyEffect": 2000.0, "netPerformancePercentWithCurrencyEffect": 0.3333,
    "dividendInBaseCurrency": 30.0, "feeInBaseCurrency": 6.0,
    "dateOfFirstActivity": "2024-03-01T00:00:00.000Z",
    "historicalData": [{"date": "2024-03-01", "marketPrice": 600.0, "averagePrice": 600.0},
                       {"date": "2026-10-01", "marketPrice": 800.0, "averagePrice": 600.0},
                       {"date": "2026-10-02", "averagePrice": 600.0}],
}
ACTIVITIES = {"activities": [
    {"date": "2025-06-01T00:00:00.000Z", "type": "BUY", "quantity": 4, "unitPrice": 650.0,
     "fee": 3.0, "currency": "EUR", "valueInBaseCurrency": 2600.0},
    {"date": "2024-03-01T00:00:00.000Z", "type": "BUY", "quantity": 6, "unitPrice": 566.67,
     "fee": 3.0, "currency": "EUR", "valueInBaseCurrency": 3400.0},
], "count": 2}


class FakeGhostfolio:
    def __init__(self):
        self.paths: list[str] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        path = unquote(request.url.path)
        self.paths.append(path)
        if path == "/api/v1/auth/anonymous":
            return httpx.Response(200, json={"authToken": "jwt"})
        assert request.headers["authorization"] == "Bearer jwt"
        if path == "/api/v1/portfolio/details":
            return httpx.Response(200, json=DETAILS)
        if path == "/api/v2/portfolio/performance":
            return httpx.Response(200, json=performance(request.url.params["range"]))
        if path.startswith("/api/v1/symbol/YAHOO/"):
            return httpx.Response(200, json=symbol(path.rsplit("/", 1)[1]))
        if path == "/api/v1/portfolio/holding/YAHOO/ASML.AS":
            return httpx.Response(200, json=HOLDING)
        if path == "/api/v1/activities":
            assert request.url.params["symbol"] == "ASML.AS"
            return httpx.Response(200, json=ACTIVITIES)
        return httpx.Response(404)


def yahoo(request: httpx.Request) -> httpx.Response:
    sym = unquote(request.url.path.rsplit("/", 1)[1])
    if sym == "^AEX":
        return httpx.Response(500)
    return httpx.Response(200, json={"chart": {"result": [{
        "meta": {"symbol": sym, "currency": "USD", "regularMarketPrice": 7666.45,
                 "regularMarketTime": 1790886937},
        "indicators": {"quote": [{"close": [7743.41, None, 7651.54, 7666.45]}]},
    }]}})


@pytest.fixture(autouse=True)
def fresh():
    holding._cache.clear()
    holding._clients.clear()


# --- summary and charts ------------------------------------------------------------------


def test_collect_adds_holding_details_and_stores_charts(store):
    portfolio = asyncio.run(
        ghostfolio.collect(CFG, "EUR", store, transport=httpx.MockTransport(FakeGhostfolio())))

    assert [h.symbol for h in portfolio.holdings] == ["ASML.AS", "NVDA"]
    asml, nvda = portfolio.holdings
    assert (asml.data_source, asml.isin, asml.currency, asml.quantity) == (
        "YAHOO", "NL0010273215", "EUR", 10)
    assert (asml.invested, asml.gain_abs, asml.gain_pct) == (6000.0, 2000.0, 33.33)
    assert asml.day_pct == 1.27
    assert asml.day_abs == round(8000 - 8000 / 1.0127, 2)
    assert nvda.day_pct == -5.0 and nvda.day_abs < 0
    assert nvda.isin is None
    assert (portfolio.invested, portfolio.gain_abs, portfolio.cash, portfolio.dividends) == (
        9100.0, 2500.0, 500.0, 42.5)

    charts = store.get_cache(ghostfolio.CHARTS_KEY)
    assert set(charts["ranges"]) == {"month", "ytd", "year", "max"}
    assert len(charts["ranges"]["max"]) == 31
    assert charts["ranges"]["month"] == charts["ranges"]["max"][-31:]
    assert charts["ranges"]["year"][0] == {"d": "2026-09-01", "v": 11010.0, "invested": 9100.0}


def test_day_abs():
    assert ghostfolio.day_abs(1010.0, 1.0) == 10.0
    assert ghostfolio.day_abs(990.0, -1.0) == -10.0
    assert ghostfolio.day_abs(500.0, 0.0) == 0.0


# --- holding detail ----------------------------------------------------------------------


def test_holding_detail_and_its_cache():
    fake = FakeGhostfolio()
    detail = asyncio.run(holding.detail(CFG, "YAHOO", "ASML.AS", httpx.MockTransport(fake)))

    assert (detail.name, detail.quantity, detail.average_price, detail.price) == (
        "ASML Holding", 10, 600.0, 800.0)
    assert (detail.gain_pct, detail.dividends, detail.fees) == (33.33, 30.0, 6.0)
    # A day without a price is left out of the chart.
    assert [p.d for p in detail.history] == ["2024-03-01", "2026-10-01"]
    assert [(a.type, a.quantity) for a in detail.activities] == [("BUY", 4), ("BUY", 6)]

    calls = len(fake.paths)
    asyncio.run(holding.detail(CFG, "YAHOO", "ASML.AS", httpx.MockTransport(fake)))
    assert len(fake.paths) == calls  # served from the cache


def test_holding_detail_thins_long_histories():
    points = [holding.PricePoint(d=f"d{i}", price=i) for i in range(1000)]
    thinned = holding._thin(points)
    assert len(thinned) == holding.MAX_POINTS and thinned[-1].d == "d999"


def test_holding_detail_rejects_odd_symbols():
    for ds, sym in [("YAHOO", "../admin"), ("yahoo", "NVDA"), ("YAHOO", "A" * 40)]:
        with pytest.raises(holding.NotFound):
            asyncio.run(holding.detail(CFG, ds, sym))


# --- indices -------------------------------------------------------------------------------


def test_indices_skip_gaps_and_failures():
    result = asyncio.run(indices.collect(CFG, httpx.MockTransport(yahoo)))
    assert [(q.symbol, q.label, q.price, q.day_pct) for q in result.indices] == [
        ("^GSPC", "S&P 500", 7666.45, 0.19)]


def test_indices_fail_when_nothing_answers():
    with pytest.raises(RuntimeError):
        asyncio.run(indices.collect(CFG, httpx.MockTransport(lambda r: httpx.Response(500))))


def test_index_parse_needs_two_closes():
    payload = {"chart": {"result": [{"meta": {"regularMarketPrice": 1.0},
                                     "indicators": {"quote": [{"close": [1.0]}]}}]}}
    assert indices.parse("^X", payload) is None
    assert indices.parse("^X", {"chart": {"result": None}}) is None


# --- endpoints -------------------------------------------------------------------------------


@pytest.fixture
def client(store):
    main.app.state.store = store
    main.app.state.config = CFG
    main.app.state.ghostfolio_transport = httpx.MockTransport(FakeGhostfolio())
    yield TestClient(main.app)
    del main.app.state.ghostfolio_transport


def test_history_endpoint(client, store):
    assert client.get("/api/portfolio/history").status_code == 503
    asyncio.run(ghostfolio.collect(CFG, "EUR", store,
                                   transport=httpx.MockTransport(FakeGhostfolio())))
    body = client.get("/api/portfolio/history?range=month").json()
    assert body["range"] == "month" and len(body["points"]) == 31
    assert client.get("/api/portfolio/history?range=decade").status_code == 422


def test_holding_endpoint(client):
    body = client.get("/api/portfolio/holdings/YAHOO/ASML.AS").json()
    assert body["symbol"] == "ASML.AS" and len(body["activities"]) == 2
    assert client.get("/api/portfolio/holdings/YAHOO/NOPE").status_code == 404
    main.app.state.ghostfolio_transport = httpx.MockTransport(lambda r: httpx.Response(500))
    holding._clients.clear()
    assert client.get("/api/portfolio/holdings/YAHOO/NVDA").status_code == 502


def test_indices_endpoint(client, store):
    assert client.get("/api/indices").status_code == 503
    store.put_cache("indices", {"as_of": "2026-10-02T08:00:00Z", "stale": False, "indices": []})
    assert client.get("/api/indices").json()["indices"] == []
