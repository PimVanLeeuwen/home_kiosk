"""The running overview (plan.md M28, step 3): runs and Runna's plan together. Made-up runs."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient

from app import main, running
from app.sources import runna, runs
from tests.test_runna import FEED
from tests.test_runs import workout

ZONE = ZoneInfo("Europe/Amsterdam")
NOW = datetime(2026, 10, 29, 18, 0, tzinfo=UTC)  # a Thursday evening


def run_on(day: date, wid: str, km: float = 5.2) -> dict:
    start = datetime(day.year, day.month, day.day, 7, 0, tzinfo=UTC)
    stamp = lambda t: t.strftime("%Y-%m-%d %H:%M:%S +0000")  # noqa: E731
    return workout(wid, start=stamp(start), end=stamp(start + timedelta(seconds=1716)),
                   distance={"qty": km, "units": "km"})


@pytest.fixture
def house(store):
    days = [date(2026, 10, 12), date(2026, 10, 14), date(2026, 10, 16),   # three runs
            date(2026, 10, 19), date(2026, 10, 21), date(2026, 10, 24),   # three runs
            date(2026, 10, 27), date(2026, 10, 29)]                       # this week so far
    runs.receive(store, {"data": {"workouts": [run_on(d, f"r{i}") for i, d in enumerate(days)]}})
    plan = runna.plan(runna.parse(FEED, ZONE), date(2026, 10, 26))
    store.put_cache(runna.CACHE_KEY, plan.model_dump(mode="json"))
    return store


def test_the_week_against_the_plan_the_totals_and_the_streak(house):
    view = running.overview(house, ZONE, NOW)

    days = {d["date"]: d for d in view["week"]}
    assert days["2026-10-27"]["planned_m"] == 8000 and days["2026-10-27"]["done_m"] == 5200
    assert days["2026-10-27"]["sessions"] == ["Threshold Intervals"]
    assert len(days["2026-10-29"]["routes"]) == 1 and len(days["2026-10-29"]["routes"][0]) <= 40
    assert days["2026-10-28"]["routes"] == []
    totals = view["totals"]
    assert totals["week_m"] == 10400 and totals["last4_m"] == 8 * 5200
    assert totals["streak_weeks"] == 2  # this week is under way with two runs
    assert view["last"]["id"] == "r7" and view["last"]["route"][0][2] is None
    assert view["last"]["session"] == "Easy Run"  # the session of the day it was run
    assert view["bests"]["5k"]["seconds"] == pytest.approx(1650, abs=10)
    assert view["bests"]["longest"]["metres"] == 5200


def test_the_next_session_waits_for_todays_run(house):
    view = running.overview(house, ZONE, NOW)
    # Today's session (07:30) is done with today's run: the next one is the weekend's.
    assert view["today"]["ran"] and view["today"]["session"]["name"] == "Easy Run"
    assert view["next"]["name"] == "Race Pace Intervals"
    morning = running.overview(house, ZONE, datetime(2026, 10, 28, 6, 0, tzinfo=UTC))
    assert morning["next"]["name"] == "Easy Run"


def test_no_runs_and_no_plan_is_an_empty_overview(store):
    view = running.overview(store, ZONE, NOW)
    assert view["last"] is None and view["next"] is None and not view["has_plan"]
    assert view["totals"]["streak_weeks"] == 0 and len(view["week"]) == 7


def test_the_route(house):
    main.app.state.store = house
    main.app.state.config = {"timezone": "Europe/Amsterdam"}
    answer = TestClient(main.app).get("/api/runs/overview").json()
    assert len(answer["week"]) == 7 and "totals" in answer


def test_runnas_steps_as_blocks_in_both_repeat_forms():
    reps = ("Intervals • 5mi\n\n1mi warm up at a conversational pace, 90s walking rest\n\n"
            "3 reps of:\n• 0.75mi at 6:50/mi, 120s walking rest\n• 0.25mi at 6:20/mi\n\n"
            "1mi cool down at a conversational pace\n\n📲 View in the Runna app: https://x")
    kinds = [b["kind"] for b in runna.blocks(reps)]
    assert kinds == ["easy", "rest"] + ["work", "rest", "work"] * 3 + ["easy"]
    assert runna.blocks(reps)[2]["pace"] == 255  # 6:50/mi as seconds per km
    dashes = ("Tempo • 6.5mi\n\n1.25mi warm up\n\nRepeat the following 4x:\n----------\n"
              "0.5mi at 6:55/mi\n0.5mi at 8:05/mi\n----------\n\n90s walking rest\n\n"
              "1.25mi cool down")
    assert [b["kind"] for b in runna.blocks(dashes)] == ["easy"] + ["work"] * 8 + ["rest", "easy"]
