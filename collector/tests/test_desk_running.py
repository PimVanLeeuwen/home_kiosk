"""The Now panel's run screens (plan.md M28, step 4). Made-up runs and plan."""

from __future__ import annotations

from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

from app import desk_running, paint_run, paint_runweek, paint_session
from app.sources import runna, runs
from tests.test_runna import FEED
from tests.test_running import run_on

ZONE = ZoneInfo("Europe/Amsterdam")


def at(day: int, hour: int = 18) -> datetime:
    return datetime(2026, 10, day, hour, 0, tzinfo=UTC)


def plan(store, today=date(2026, 10, 26)):
    sessions = runna.parse(FEED, ZONE)
    store.put_cache(runna.CACHE_KEY, runna.plan(sessions, today).model_dump(mode="json"))


def test_the_last_run_for_two_days_with_its_route_for_the_light(store):
    runs.receive(store, {"data": {"workouts": [run_on(date(2026, 10, 27), "r1", 7.3)]}})

    screen = desk_running.run_screen(store, ZONE, at(27))
    texts = [label["text"] for label in screen["labels"]]
    assert screen["present"] and "7,3" in texts and "km" in texts and "/KM" in texts
    assert len(screen["path"]) == desk_running.PATH_POINTS
    x1, y1, x2, y2 = desk_running.ROUTE_BOX
    assert all(x1 - 1 <= x <= x2 + 1 and y1 - 1 <= y <= y2 + 1 for x, y in screen["path"])
    assert desk_running.run_screen(store, ZONE, at(28))["present"]       # the day after
    assert not desk_running.run_screen(store, ZONE, at(29))["present"]   # gone after two days
    assert paint_run.paint_run(paint_run.inputs(screen, at(27)), store).size == (720, 720)


def test_the_unit_follows_the_number_in_the_clock_font(store):
    runs.receive(store, {"data": {"workouts": [run_on(date(2026, 10, 27), "r1", 10.4)]}})
    labels = desk_running.run_screen(store, ZONE, at(27))["labels"]
    number = next(lb for lb in labels if lb["text"] == "10,4")
    unit = next(lb for lb in labels if lb["text"] == "km")
    width = sum(desk_running.CLOCK_ADVANCE[c] for c in "10,4")
    assert unit["x"] == number["x"] + round(width)


def test_the_week_with_a_plan_or_a_run_this_week(store):
    assert not desk_running.runweek_screen(store, ZONE, at(27))["present"]
    plan(store)
    runs.receive(store, {"data": {"workouts": [run_on(date(2026, 10, 27), "r1", 5.2)]}})

    screen = desk_running.runweek_screen(store, ZONE, at(28))
    texts = [label["text"] for label in screen["labels"]]
    assert screen["present"] and "5,2 km" in texts and "of 23,0 km planned by Runna" in texts
    assert [d["today"] for d in screen["week"]].index(True) == 2  # Wednesday
    assert screen["week"][1]["runs"] == ["r1"]
    picture = paint_runweek.paint_runweek(paint_runweek.inputs(screen, at(28)), store)
    assert picture.size == (720, 720)


def test_the_next_session_the_day_before_and_on_the_day(store):
    plan(store)
    # Monday evening: tomorrow's Threshold Intervals.
    screen = desk_running.session_screen(store, ZONE, at(26))
    texts = [label["text"] for label in screen["labels"]]
    assert screen["present"] and "NEXT RUN · TOMORROW" in texts
    assert "Threshold Intervals" in texts and "8,0 km · 45m - 50m" in texts
    assert [b["kind"] for b in screen["blocks"]][:2] == ["easy", "rest"]
    assert paint_session.paint_session(paint_session.inputs(screen, at(26))).size == (720, 720)
    # Wednesday evening: Thursday's run is tomorrow. Sunday's is not there on Friday (two days
    # ahead), and is on Saturday.
    assert desk_running.session_screen(store, ZONE, at(28))["present"]
    plan(store, date(2026, 10, 30))
    friday = desk_running.session_screen(store, ZONE, datetime(2026, 10, 30, 8, tzinfo=UTC))
    saturday = desk_running.session_screen(store, ZONE, datetime(2026, 10, 31, 8, tzinfo=UTC))
    assert not friday["present"]
    assert "Race Pace Intervals" in [lb["text"] for lb in saturday["labels"]]
    plan(store, date(2026, 11, 2))
    later = desk_running.session_screen(store, ZONE, datetime(2026, 11, 2, 8, tzinfo=UTC))
    assert not later["present"]  # the next one (the race) is weeks away
