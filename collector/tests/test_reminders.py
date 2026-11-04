from __future__ import annotations

import asyncio
from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient

from app import main, reminders
from app.alerts import core
from app.reminders import Draft, Repeat

AMS = ZoneInfo("Europe/Amsterdam")
CFG = {"timezone": "Europe/Amsterdam"}
TUE = date(2026, 11, 3)


def draft(start=TUE, at=None, notify="at", **repeat) -> Draft:
    return Draft(title="Bins out", start=start, at=at, notify=notify, repeat=Repeat(**repeat))


def days(r: Draft, first: date, count: int) -> list[str]:
    return [(first + timedelta(days=i)).isoformat() for i in range(count)
            if reminders.occurs(r, first + timedelta(days=i))]


def test_a_reminder_without_a_repeat_falls_once():
    assert days(draft(), TUE - timedelta(days=3), 10) == ["2026-11-03"]
    assert reminders.next_day(draft(), TUE + timedelta(days=1)) is None


def test_every_n_days_or_weeks_counts_from_its_date():
    assert days(draft(kind="every", every=3), TUE - timedelta(days=1), 8) == [
        "2026-11-03", "2026-11-06", "2026-11-09"]
    assert days(draft(kind="every", every=2, unit="weeks"), TUE, 30) == [
        "2026-11-03", "2026-11-17", "2026-12-01"]


def test_weekly_falls_on_the_chosen_days_and_needs_one():
    assert days(draft(kind="weekly", weekdays=[3, 0, 0]), TUE, 7) == ["2026-11-05", "2026-11-09"]
    with pytest.raises(ValueError):
        draft(kind="weekly", weekdays=[])


def test_monthly_falls_on_its_day_or_the_last_day():
    monthly = draft(start=date(2026, 1, 31), kind="monthly", day=31)
    assert reminders.next_day(monthly, date(2026, 2, 1)) == date(2026, 2, 28)
    assert reminders.next_day(monthly, date(2026, 4, 1)) == date(2026, 4, 30)
    last = draft(start=date(2026, 1, 1), kind="monthly", day="last")
    assert reminders.next_day(last, date(2026, 2, 1)) == date(2026, 2, 28)


def test_yearly_falls_on_its_date_and_29_february_on_the_28th():
    leap = draft(start=date(2024, 2, 29), kind="yearly")
    assert reminders.next_day(leap, date(2026, 1, 1)) == date(2026, 2, 28)
    assert reminders.next_day(leap, date(2028, 1, 1)) == date(2028, 2, 29)


def test_when_the_message_goes_out():
    timed = draft(at="07:30")
    at = reminders.notify_at
    assert at(timed, TUE, AMS) == datetime(2026, 11, 3, 7, 30, tzinfo=AMS)
    assert at(draft(), TUE, AMS) == datetime(2026, 11, 3, 8, 0, tzinfo=AMS)  # no time: 08:00
    assert at(draft(at="07:30", notify="hour"), TUE, AMS) == datetime(2026, 11, 3, 6, 30,
                                                                     tzinfo=AMS)
    assert at(draft(notify="evening"), TUE, AMS) == datetime(2026, 11, 2, 20, 0, tzinfo=AMS)
    assert at(draft(notify="none"), TUE, AMS) is None
    with pytest.raises(ValueError):
        draft(notify="hour")  # an hour before what?


@pytest.fixture
def rem_store(store):
    reminders.ensure_tables(store)
    return store


def test_each_message_goes_out_once_and_not_for_a_day_ticked_off(rem_store, monkeypatch):
    sent = []

    async def notify(store, cfg, **kw):
        sent.append((kw["category"], kw["title"], kw["body"]))

    monkeypatch.setattr(core, "notify", notify)
    bins = reminders.add(rem_store, draft(at="07:30", kind="weekly", weekdays=[1]))
    reminders.add(rem_store, Draft(title="Call Mama", start=TUE + timedelta(days=1),
                                   notify="evening"))
    run = lambda now: asyncio.run(reminders.send_due(CFG, rem_store, now))  # noqa: E731

    assert run(datetime(2026, 11, 3, 6, 29, tzinfo=UTC)) == 0  # 07:29 in Amsterdam
    assert run(datetime(2026, 11, 3, 6, 30, tzinfo=UTC)) == 1
    assert run(datetime(2026, 11, 3, 6, 31, tzinfo=UTC)) == 0  # already sent
    assert sent == [("reminders", "Bins out", "Today at 07:30")]

    assert run(datetime(2026, 11, 3, 19, 0, tzinfo=UTC)) == 1  # 20:00, the evening before
    assert sent[-1] == ("reminders", "Call Mama", "Tomorrow")

    reminders.set_done(rem_store, bins.id, TUE + timedelta(days=7), True)
    assert run(datetime(2026, 11, 10, 6, 30, tzinfo=UTC)) == 0  # ticked off beforehand


def test_a_message_missed_by_hours_is_not_sent_late(rem_store, monkeypatch):
    monkeypatch.setattr(core, "notify", lambda *a, **k: asyncio.sleep(0))
    reminders.add(rem_store, draft(at="07:30"))
    assert reminders.due(rem_store, datetime(2026, 11, 3, 8, 29, tzinfo=UTC), AMS) != []
    assert reminders.due(rem_store, datetime(2026, 11, 3, 8, 31, tzinfo=UTC), AMS) == []


@pytest.fixture
def client(rem_store):
    main.app.state.store = rem_store
    main.app.state.config = CFG
    return TestClient(main.app, headers={"origin": "http://testserver"})


def test_the_page_adds_changes_ticks_off_and_deletes(client):
    body = {"title": "Bins out", "start": "2026-11-03", "at": "07:30",
            "repeat": {"kind": "every", "every": 2, "unit": "weeks"}, "notify": "evening"}
    [made] = client.post("/api/reminders", json=body).json()["reminders"]
    assert (made["title"], made["repeat"]["every"], made["notify"]) == ("Bins out", 2, "evening")
    assert made["next"] >= "2026-11-03"

    changed = client.put(f"/api/reminders/{made['id']}", json=body | {"title": "Paper out"})
    assert changed.json()["reminders"][0]["title"] == "Paper out"

    tick = client.post(f"/api/reminders/{made['id']}/done", json={"day": "2026-11-17"})
    assert tick.status_code == 200
    assert client.post(f"/api/reminders/{made['id']}/done",
                       json={"day": "2026-11-10"}).status_code == 422  # not its day
    assert client.delete(f"/api/reminders/{made['id']}").json()["reminders"] == []
    assert client.delete(f"/api/reminders/{made['id']}").status_code == 404


def test_the_page_checks_what_it_is_sent(client):
    good = {"title": "Bins out", "start": "2026-11-03"}
    assert client.post("/api/reminders", json=good | {"title": "  "}).status_code == 422
    assert client.post("/api/reminders", json=good | {"at": "25:00"}).status_code == 422
    assert client.post("/api/reminders", json=good | {"repeat": {"kind": "weekly"}}
                       ).status_code == 422
    other = TestClient(main.app, headers={"origin": "http://evil.example"})
    assert other.post("/api/reminders", json=good).status_code == 403


def test_today_lists_timed_ones_first_with_their_state(rem_store):
    a = reminders.add(rem_store, Draft(title="water plants", start=TUE))
    reminders.add(rem_store, Draft(title="Bins out", start=TUE, at="07:30"))
    reminders.set_done(rem_store, a.id, TUE, True)
    assert [(r["title"], r["at"], r["done"]) for r in reminders.today(rem_store, TUE)] == [
        ("Bins out", "07:30", False), ("water plants", None, True)]
