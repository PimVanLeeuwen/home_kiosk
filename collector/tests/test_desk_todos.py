from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

from app import desk, todos
from app.desk_todos import due_word, todos_screen

AMS = ZoneInfo("Europe/Amsterdam")
CFG = {"timezone": "Europe/Amsterdam"}
NOW = datetime(2026, 11, 18, 23, 30, tzinfo=UTC)  # already the 19th in Amsterdam
DAY = date(2026, 11, 19)


def test_the_due_word_counts_from_today():
    assert due_word(None, DAY) == ""
    assert due_word(DAY, DAY) == "Today"
    assert due_word(DAY + timedelta(days=1), DAY) == "Tomorrow"
    assert due_word(DAY - timedelta(days=1), DAY) == "Yesterday"
    assert due_word(DAY - timedelta(days=4), DAY) == "4 days late"
    assert due_word(date(2026, 11, 22), DAY) == "Sun 22 Nov"


def test_the_screen_stays_out_with_nothing_open(store):
    assert todos_screen(store, AMS, NOW) == {"kind": "todos", "stale": False, "present": False}


def test_the_screen_lists_them_in_order_with_their_due_word_in_latin1(store):
    todos.ensure_tables(store)
    todos.add(store, todos.Draft(title="Fix the shed – door"))
    todos.add(store, todos.Draft(title="Tax return 🧾", due=DAY - timedelta(days=2), high=True))
    todos.add(store, todos.Draft(title="Ring the plumber", note="kitchen tap", due=DAY))

    screen = todos_screen(store, AMS, NOW)

    assert screen == {
        "kind": "todos", "stale": False, "present": True, "title": "TODOS · 3 OPEN · 1 LATE",
        "todos": [
            {"title": "Tax return", "due": "2 days late", "state": "overdue", "high": True},
            {"title": "Ring the plumber", "due": "Today", "state": "today", "high": False},
            {"title": "Fix the shed - door", "due": "", "state": "", "high": False},
        ],
        "more": 0,
    }


def test_the_panel_gets_up_to_twelve_to_turn_through(store):
    todos.ensure_tables(store)
    for i in range(15):
        todos.add(store, todos.Draft(title=f"Todo {i}"))

    screen = todos_screen(store, AMS, NOW)

    assert screen["title"] == "TODOS · 15 OPEN"
    assert len(screen["todos"]) == 12 and screen["more"] == 3


def test_the_now_panel_shows_it_after_the_calendar_and_drops_it_before(store):
    todos.ensure_tables(store)
    todos.add(store, todos.Draft(title="Fix the shed"))

    kinds = [s["kind"] for s in desk.answer(CFG, store, "now", NOW)["screens"]]

    assert kinds.index("todos") == kinds.index("agenda") + 1
    assert desk.DROP_FIRST.index("todos") < desk.DROP_FIRST.index("agenda")
