from __future__ import annotations

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import icalendar

from app import desk_pieces
from app.sources import agenda, countdown

ZONE = ZoneInfo("Europe/Amsterdam")
INFO = agenda.CalendarInfo(id="c1", name="Home", color="#e6965a", kind="icloud")


def calendar(*events):
    cal = icalendar.Calendar()
    for summary, start, rule in events:
        e = icalendar.Event()
        e.add("summary", summary)
        e.add("dtstart", start)
        if rule:
            e.add("rrule", rule)
        cal.add_component(e)
    return cal


def test_only_marked_titles_count_and_lose_their_marker():
    assert countdown.marked("Lisbon ⏳") == "Lisbon"
    assert countdown.marked("Lisbon #Countdown") == "Lisbon"
    assert countdown.marked("Dentist") is None


def test_marked_events_over_the_year_repeating_ones_unfolded():
    start = datetime(2026, 10, 26, tzinfo=ZONE)
    cal = calendar(("Lisbon ⏳", datetime(2026, 11, 14, 9, tzinfo=ZONE), None),
                   ("Dentist", datetime(2026, 11, 2, 9, tzinfo=ZONE), None),
                   ("Anna's birthday #countdown", datetime(2020, 3, 3).date(), {"freq": "yearly"}))
    events = countdown.found([cal], INFO, start, start + timedelta(days=365))
    assert sorted((e["title"], e["date"]) for e in events) == [
        ("Anna's birthday", "2027-03-03"), ("Lisbon", "2026-11-14")]
    assert events[0]["colour"] == "#e6965a"


def test_the_screen_counts_the_days_and_names_the_next(store):
    store.put_cache(countdown.CACHE_KEY, {"as_of": "x", "stale": False, "events": [
        {"title": "Lisbon", "date": "2026-11-14", "colour": "#e6965a", "calendar": "Home"},
        {"title": "Anna's birthday", "date": "2027-03-03", "colour": "#6aa8f0",
         "calendar": "Home"}]})
    now = datetime(2026, 10, 26, 8, tzinfo=UTC)

    screen = desk_pieces.countdown_screen(store, ZONE, now)

    texts = [label["text"] for label in screen["labels"]]
    assert screen["days"] == 19 and "19" in texts and "days to" in texts and "Lisbon" in texts
    assert "Then Anna's birthday in 128 days" in texts
    on_the_day = desk_pieces.countdown_screen(store, ZONE, datetime(2026, 11, 14, 8, tzinfo=UTC))
    assert "Today" in [label["text"] for label in on_the_day["labels"]]
    gone = desk_pieces.countdown_screen(store, ZONE, datetime(2027, 4, 1, 8, tzinfo=UTC))
    assert gone["present"] is False


def test_the_hub_serves_the_countdowns(store):
    from fastapi.testclient import TestClient

    from app import main
    main.app.state.store = store
    client = TestClient(main.app)
    assert client.get("/api/countdown").status_code == 503
    store.put_cache(countdown.CACHE_KEY, {"as_of": "x", "stale": False, "events": [
        {"title": "Lisbon", "date": "2026-11-14", "colour": "#e6965a", "calendar": "Home"}]})
    assert client.get("/api/countdown").json()["events"][0]["title"] == "Lisbon"
