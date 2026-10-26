from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

from app import desk, desk_code

ZONE = ZoneInfo("Europe/Amsterdam")
NOW = datetime(2026, 10, 21, 12, 0, tzinfo=UTC)  # a Wednesday
START = date(2026, 7, 6)  # the Monday 15 weeks before this one


def activity(counts: list[int]) -> dict:
    days = [
        {
            "day": (START + timedelta(days=i)).isoformat(),
            "count": c,
            "level": 0 if c == 0 else 1 if c < 10 else 2 if c < 35 else 3 if c < 80 else 4,
        }
        for i, c in enumerate(counts)
    ]
    return {"login": "me", "total": sum(counts), "days": days}


# 15 full weeks, then Monday to Wednesday of this one: quiet early, busier later.
COUNTS = [0, 2, 0, 0, 0, 0, 0] * 10 + [5, 40, 10, 3, 0, 0, 0] * 5 + [20, 30, 0]


def screen(store, counts=COUNTS):
    store.put_cache(
        "repos",
        {"as_of": NOW.isoformat(), "stale": False, "groups": [], "activity": activity(counts)},
    )
    return desk_code.code_screen(store, ZONE, NOW)


def test_the_grid_runs_monday_first_up_to_today(store):
    s = screen(store)
    assert (s["kind"], s["present"], s["title"], s["right"]) == (
        "code",
        True,
        "CODE · 16 WEEKS",
        f"{sum(COUNTS)} CONTRIBUTIONS",
    )
    assert len(s["levels"]) == 108 and s["levels"][-3:] == [2, 2, 0]
    assert s["months"] == [
        {"week": 0, "name": "Jul"},
        {"week": 4, "name": "Aug"},
        {"week": 9, "name": "Sep"},
        {"week": 13, "name": "Oct"},
    ]


def test_each_week_is_a_bar_against_the_busiest(store):
    s = screen(store)
    assert len(s["weeks"]) == 16
    assert s["weeks"][0] == round(2 / 58 * 1000) and max(s["weeks"]) == 1000
    assert s["weeks"][-1] == round(50 / 58 * 1000)
    assert s["this_week"] == "this week 50"


def test_the_streak_and_the_busiest_weekday(store):
    s = screen(store)
    assert s["streak"] == "2-day streak"  # nothing yet today: Monday and Tuesday count
    assert s["busiest"] == "busiest on Tuesdays"
    assert screen(store, COUNTS[:-1] + [7])["streak"] == "3-day streak"


def test_no_calendar_yet(store):
    assert desk_code.code_screen(store, ZONE, NOW) == {
        "kind": "code",
        "stale": False,
        "present": False,
    }


def test_a_running_pipeline_takes_house_over_alone(store):
    screen(store)
    store.put_cache(
        "pipelines",
        {
            "as_of": NOW.isoformat(),
            "stale": False,
            "repos": [
                {
                    "repo": "x/y",
                    "name": "y",
                    "branch": "main",
                    "recent": [],
                    "run": {
                        "number": 1,
                        "url": "",
                        "state": "running",
                        "started_at": NOW.isoformat(),
                        "ended_at": None,
                        "approval_since": None,
                        "seconds": 60,
                        "usual": [],
                        "commit": "",
                        "author": None,
                        "sha": "",
                        "failed": None,
                        "jobs": [],
                    },
                }
            ],
        },
    )
    kinds = [
        s["kind"]
        for s in desk.answer({"timezone": "Europe/Amsterdam"}, store, "house", NOW)["screens"]
    ]
    assert kinds == ["pipeline"]

    store.put_cache("pipelines", {"as_of": NOW.isoformat(), "stale": False, "repos": []})
    kinds = [
        s["kind"]
        for s in desk.answer({"timezone": "Europe/Amsterdam"}, store, "house", NOW)["screens"]
    ]
    assert kinds == ["pipelines", "nas", "orbit", "code", "sites", "services", "tailnet", "money",
                     "movers", "media", "backups", "alerts"]
