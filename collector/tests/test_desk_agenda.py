from __future__ import annotations

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from app.desk_agenda import agenda_screen

AMS = ZoneInfo("Europe/Amsterdam")
NOW = datetime(2026, 10, 19, 8, 48, tzinfo=AMS)


def event(title, start, end, calendar="Work", color="#ff8d28"):
    return {"calendar_id": "c", "calendar": calendar, "color": color, "title": title,
            "start": start, "end": end, "all_day": False}


def put(store, events=(), all_day=(), date="2026-10-19", stale=False):
    store.put_cache("calendar", {"as_of": NOW.isoformat(), "stale": stale, "date": date,
                                 "events": list(events), "all_day": list(all_day), "errors": {}})


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
