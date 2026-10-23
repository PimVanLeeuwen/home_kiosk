from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

from app import desk_money

ZONE = ZoneInfo("Europe/Amsterdam")
NOW = datetime(2026, 10, 23, 12, 0, tzinfo=UTC)


def days(values, invested, end=date(2026, 10, 23)):
    start = end - timedelta(days=len(values) - 1)
    return [{"d": (start + timedelta(days=i)).isoformat(), "v": v, "invested": inv}
            for i, (v, inv) in enumerate(zip(values, invested, strict=True))]


def put(store, month, year=None, total=None, today=0.07):
    store.put_cache("portfolio_charts", {"as_of": NOW.isoformat(), "stale": False,
                                         "ranges": {"month": month, "year": year or month,
                                                    "max": total or year or month}})
    store.put_cache("portfolio", {"change": {"day_pct": today}})
    return desk_money.money_screen(store, ZONE, NOW)


def test_periods_leave_deposits_out_and_send_no_amounts(store):
    # 1000 invested and worth 1000; a deposit of 500 on day 20; a 10% rise in the end.
    values = [1000.0] * 20 + [1500.0] * 10 + [1650.0]
    invested = [1000.0] * 20 + [1500.0] * 11
    s = put(store, days(values, invested))
    assert (s["kind"], s["present"], s["today"], s["today_up"]) == (
        "money", True, "TODAY +0.1%", True)
    month = next(p for p in s["periods"] if p["key"] == "1M")
    assert month["change"] == "+10.0%" and month["up"] is True  # 150 gain over 1000 + 500
    assert month["points"][0] == 0 and month["points"][-1] == 1000
    assert (month["from"], month["to"], month["high"]) == ("23 Sep", "Today", "+10.0%")
    week = next(p for p in s["periods"] if p["key"] == "1W")
    assert len(week["points"]) == 8 and week["from"] == "16 Oct"
    # No euro amount anywhere in what the panel gets.
    assert "1650" not in str(s) and "1500" not in str(s)


def test_a_long_history_is_thinned_and_a_loss_is_down(store):
    values = [2000.0 - i for i in range(300)]
    s = put(store, days(values[-31:], [1000.0] * 31), year=days(values, [1000.0] * 300))
    year = next(p for p in s["periods"] if p["key"] == "1Y")
    assert len(year["points"]) == desk_money.MAX_POINTS and year["up"] is False
    assert year["change"].startswith("-") and year["high_at"] == 0


def test_percent_words():
    assert [desk_money.pct(x) for x in (4.21, -0.66, 0.01, 0)] == ["+4.2%", "-0.7%", "0.0%", "0.0%"]


def test_nothing_read_yet(store):
    assert desk_money.money_screen(store, ZONE, NOW) == {
        "kind": "money", "stale": False, "present": False}
