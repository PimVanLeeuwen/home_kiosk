from __future__ import annotations

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from app import desk_movers

ZONE = ZoneInfo("Europe/Amsterdam")
NOW = datetime(2026, 10, 22, 12, 0, tzinfo=UTC)


def holding(symbol: str, weight: float, move: float, name: str = "") -> dict:
    return {"symbol": symbol, "name": name or symbol, "weight_pct": weight, "day_pct": move}


HOLDINGS = [holding("NVDA", 22.02, 2.54, "NVIDIA Corporation"), holding("XDWT.L", 17.48, 1.32),
            holding("ASML.AS", 16.68, 2.64), holding("VUSD.L", 16.02, 0.41),
            holding("AAPL", 10.24, 1.32), holding("TSM", 8.57, 1.6), holding("AMZN", 2.6, -0.1),
            holding("CRM", 2.4, -0.27), holding("INGA.AS", 1.67, 1.48),
            holding("AIAA.DE", 1.57, 0.83), holding("MDLZ", 0.62, -1.95)]
INDICES = [{"symbol": "^GSPC", "label": "S&P 500", "price": 1, "day_pct": 0.58},
           {"symbol": "^NDX", "label": "Nasdaq 100", "price": 1, "day_pct": 0.91},
           {"symbol": "^AEX", "label": "AEX", "price": 1, "day_pct": -0.22}]


def screen(store, holdings=HOLDINGS, day=-0.14):
    store.put_cache("portfolio", {"as_of": NOW.isoformat(), "stale": False,
                                  "holdings": holdings, "change": {"day_pct": day}})
    store.put_cache("indices", {"as_of": NOW.isoformat(), "stale": False, "indices": INDICES})
    return desk_movers.movers_screen(store, ZONE, NOW)


def test_tiles_by_weight_with_the_small_ones_together(store):
    s = screen(store)
    assert (s["kind"], s["present"], s["title"], s["total"], s["total_up"]) == (
        "movers", True, "TOP MOVERS · TODAY", "portfolio -0.14%", False)
    tickers = [t["ticker"] for t in s["tiles"]]
    assert tickers == ["NVDA", "XDWT", "ASML", "VUSD", "AAPL", "TSM", "AMZN", "CRM", "+3"]
    nvda, others = s["tiles"][0], s["tiles"][-1]
    assert (nvda["change"], nvda["move"], nvda["size"], nvda["name"]) == (
        "+2.54%", 254, "lg", "NVIDIA Corporation")
    # The others move together, weighted: (1.67 * 1.48 + 1.57 * 0.83 - 0.62 * 1.95) / 3.86.
    assert others["move"] == round((1.67 * 1.48 + 1.57 * 0.83 - 0.62 * 1.95) / 3.86 * 100)


def test_the_tiles_fill_the_box_without_overlap(store):
    tiles = screen(store)["tiles"]
    assert sum(t["w"] * t["h"] for t in tiles) == desk_movers.BOX_W * desk_movers.BOX_H
    for t in tiles:
        assert desk_movers.BOX_X <= t["x"] and t["x"] + t["w"] <= desk_movers.BOX_X + 648
        assert desk_movers.BOX_Y <= t["y"] and t["y"] + t["h"] <= desk_movers.BOX_Y + 540


def test_the_indices_below(store):
    assert screen(store)["indices"] == [
        {"label": "S&P 500", "change": "+0.58%", "up": True},
        {"label": "Nasdaq 100", "change": "+0.91%", "up": True},
        {"label": "AEX", "change": "-0.22%", "up": False}]


def test_one_small_holding_keeps_its_ticker(store):
    s = screen(store, HOLDINGS[:3] + [holding("MDLZ", 0.62, -1.95)])
    assert s["tiles"][-1]["ticker"] == "MDLZ"


def test_squarify_matches_the_hub():
    # Two equal halves of a wide box side by side, as web/src/lib/treemap.ts lays them out.
    assert desk_movers.squarify([1, 1], 200, 100) == [(0, 0, 100, 100), (100, 0, 100, 100)]
    assert desk_movers.squarify([], 200, 100) == []


def test_no_portfolio_yet(store):
    assert desk_movers.movers_screen(store, ZONE, NOW) == {
        "kind": "movers", "stale": False, "present": False}
