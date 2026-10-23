from __future__ import annotations

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from app.desk_agenda import agenda_screen

AMS = ZoneInfo("Europe/Amsterdam")
NOW = datetime(2026, 10, 19, 8, 48, tzinfo=AMS)


def event(title, start, end, calendar="Work", color="#ff8d28"):
    return {"calendar_id": "c", "calendar": calendar, "color": color, "title": title,
            "start": start, "end": end, "all_day": False}


def put(store, events=(), all_day=(), date="2026-10-19", stale=False, tomorrow=None):
    store.put_cache("calendar", {"as_of": NOW.isoformat(), "stale": stale, "date": date,
                                 "events": list(events), "all_day": list(all_day), "errors": {},
                                 "tomorrow": tomorrow})


TOMORROW = {"date": "2026-10-20", "all_day": [],
            "events": [event("Gym", "2026-10-20T07:30:00+02:00", "2026-10-20T08:30:00+02:00",
                             "Personal", "#ffb86b"),
                       event("Standup", "2026-10-20T09:30:00+02:00", "2026-10-20T10:00:00+02:00"),
                       event("Lunch", "2026-10-20T12:30:00+02:00", "2026-10-20T13:30:00+02:00"),
                       event("Late", "2026-10-20T20:00:00+02:00", "2026-10-20T21:00:00+02:00")]}


def screen(store, now=NOW):
    return agenda_screen(store, AMS, now.astimezone(UTC))


def test_hidden_on_a_day_without_events_or_with_yesterdays_answer(store):
    assert screen(store) == {"kind": "agenda", "stale": False, "present": False}
    put(store)
    assert screen(store)["present"] is False
    put(store, [event("Standup", "2026-10-18T09:30:00+02:00", "2026-10-18T10:00:00+02:00")],
        date="2026-10-18")
    assert screen(store)["present"] is False


def test_events_come_ready_for_the_ribbon_and_the_countdown(store):
    put(store, [event("Standup", "2026-10-19T09:30:00+02:00", "2026-10-19T10:00:00+02:00"),
                event("Dentist", "2026-10-19T16:00:00+02:00", "2026-10-19T16:45:00+02:00",
                      "Personal", "#ffb86b")],
        all_day=[{**event("Birthday Sanne", None, None, "Family", "#c8a0ff"), "all_day": True}])
    s = screen(store)
    assert s["present"] and s["title"] == "Today · Mon 19 Oct" and s["count"] == "3 events"
    standup = s["events"][0]
    assert standup["start"] == "09:30" and standup["end"] == "10:00"
    assert (standup["start_minute"], standup["end_minute"]) == (570, 600)
    assert standup["start_at"] == round(datetime(2026, 10, 19, 9, 30, tzinfo=AMS).timestamp())
    assert s["events"][1]["calendar"] == "Personal"
    assert s["all_day"] == [{"title": "Birthday Sanne", "color": "#c8a0ff"}]


def test_an_event_from_an_earlier_day_starts_the_ribbon_at_midnight(store):
    put(store, [event("Away", "2026-10-16T11:00:00+02:00", "2026-10-19T12:00:00+02:00",
                      "Samen V2 ❤️❤️", "#ff383c")])
    (away,) = screen(store)["events"]
    assert (away["start"], away["start_minute"], away["end_minute"]) == ("", 0, 720)
    assert away["calendar"] == "Samen V2"


def test_today_stays_while_something_is_left(store):
    put(store, [event("Standup", "2026-10-19T09:30:00+02:00", "2026-10-19T10:00:00+02:00")],
        tomorrow=TOMORROW)
    s = screen(store)
    assert s["mode"] == "today" and "tomorrow" not in s


def test_once_today_is_done_tomorrows_first_events(store):
    put(store, [event("Standup", "2026-10-19T09:30:00+02:00", "2026-10-19T10:00:00+02:00")],
        all_day=[{**event("Birthday Sanne", None, None, "Family", "#c8a0ff"), "all_day": True}],
        tomorrow=TOMORROW)
    s = screen(store, datetime(2026, 10, 19, 18, 0, tzinfo=AMS))  # the birthday does not hold it
    assert (s["mode"], s["today_line"]) == ("tomorrow", "Nothing more today")
    later = s["tomorrow"]
    assert (later["title"], later["count"]) == ("Tomorrow · Tue 20 Oct", "4 events")
    assert [(e["title"], e["start"], e["end"]) for e in later["events"]] == [
        ("Gym", "07:30", "08:30"), ("Standup", "09:30", "10:00"), ("Lunch", "12:30", "13:30")]
    assert s["title"] == "Today · Mon 19 Oct"  # today's fields stay, for older panels


def test_a_day_without_events_shows_tomorrow_and_hides_when_both_are_empty(store):
    put(store, tomorrow=TOMORROW)
    s = screen(store)
    assert (s["present"], s["mode"], s["today_line"]) == (True, "tomorrow", "Nothing today")
    assert s["title"] == "Tomorrow · Tue 20 Oct"
    put(store, tomorrow={**TOMORROW, "events": []})
    assert screen(store)["present"] is False
    put(store, tomorrow={**TOMORROW, "date": "2026-10-21"})  # not tomorrow's answer
    assert screen(store)["present"] is False


def test_a_done_day_without_tomorrow_stays_as_it_was(store):
    put(store, [event("Standup", "2026-10-19T09:30:00+02:00", "2026-10-19T10:00:00+02:00")])
    s = screen(store, datetime(2026, 10, 19, 18, 0, tzinfo=AMS))
    assert s["mode"] == "today" and s["present"] is True
