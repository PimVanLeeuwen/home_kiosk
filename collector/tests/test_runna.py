"""Runna's plan from its Calendar Sync feed (plan.md M28, step 2). Made-up sessions."""

from __future__ import annotations

import asyncio
from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

import httpx
import pytest
from fastapi.testclient import TestClient

from app import main
from app.sources import runna

TZ = ZoneInfo("Europe/Amsterdam")
SECRET = "https://cal.runna.example/feed/s3cret-token.ics"
CFG = {"running": {"runna_feed": SECRET.replace("https://", "webcal://")}}

FEED = """BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Runna//EN
BEGIN:VEVENT
UID:UPCOMING_PLAN_WORKOUT-a1
DTSTAMP:20261020T000000Z
DTSTART;VALUE=DATE:20261027
DTEND;VALUE=DATE:20261028
SUMMARY:🏃 Threshold Intervals • 8km
DESCRIPTION:Intervals • 8km • 45m - 50m\\n\\n2km warm up at a conversational pac
 e\\, 90s walking rest\\n\\n4 reps of:\\n• 800m at 4:05/km\\, 90s walking rest\\n\\n
 1.5km cool down at a conversational pace (or slower!)\\n\\n📲 View in the Runna app
 : https://runna.example/w/a1
X-WORKOUT-ESTIMATED-DURATION:2850
END:VEVENT
BEGIN:VEVENT
UID:UPCOMING_PLAN_WORKOUT-a2
DTSTAMP:20261020T000000Z
DTSTART:20261029T063000Z
DTEND:20261029T071000Z
SUMMARY:🏃 Easy Run • 3.1mi
DESCRIPTION:Easy Run • 3.1mi • 30m - 35m\\n\\n3.1mi easy run at a conversational pace
X-WORKOUT-ESTIMATED-DURATION:1950
END:VEVENT
BEGIN:VEVENT
UID:UPCOMING_PLAN_WORKOUT-a3
DTSTAMP:20261020T000000Z
DTSTART;VALUE=DATE:20261101
DTEND;VALUE=DATE:20261102
SUMMARY:🏃 Race Pace Intervals • 10km
DESCRIPTION:Intervals • 10km • 55m - 1h0m
END:VEVENT
BEGIN:VEVENT
UID:UPCOMING_PLAN_WORKOUT-a4
DTSTAMP:20261020T000000Z
DTSTART;VALUE=DATE:20261213
DTEND;VALUE=DATE:20261214
SUMMARY:🏁 Half Marathon • 21.1km
DESCRIPTION:Race • 21.1km • 1h40m - 1h50m
END:VEVENT
BEGIN:VEVENT
UID:UPCOMING_PLAN_WORKOUT-old
DTSTAMP:20261020T000000Z
DTSTART;VALUE=DATE:20261020
DTEND;VALUE=DATE:20261021
SUMMARY:🏃 Long Run • 12km
DESCRIPTION:Long Run • 12km • 1h10m - 1h15m
END:VEVENT
END:VCALENDAR
"""


def test_sessions_with_their_distance_steps_and_time():
    sessions = runna.parse(FEED, TZ)
    first = sessions[1]
    assert (first.name, first.kind, first.distance_m, first.estimate, first.estimate_s) == (
        "Threshold Intervals", "Intervals", 8000.0, "45m - 50m", 2850)
    assert first.time is None and first.date == "2026-10-27"
    assert first.steps == ["2km warm up at a conversational pace, 90s walking rest", "4 reps of:",
                           "800m at 4:05/km, 90s walking rest",
                           "1.5km cool down at a conversational pace (or slower!)"]
    easy = sessions[2]
    assert easy.time == "07:30" and easy.distance_m == pytest.approx(4989, abs=1)
    races = [s.name for s in sessions if s.race]
    assert races == ["Half Marathon"]  # "Race Pace Intervals" is training


def test_the_plan_from_today_with_the_week_and_the_race():
    plan = runna.plan(runna.parse(FEED, TZ), date(2026, 10, 26))
    assert [s.uid.rsplit("-", 1)[1] for s in plan.sessions] == ["a1", "a2", "a3", "a4"]
    assert [d["date"] for d in plan.week][0] == "2026-10-26"
    planned = {d["date"]: d["planned_m"] for d in plan.week}
    assert planned["2026-10-27"] == 8000 and planned["2026-10-26"] == 0
    assert round(sum(planned.values())) == round(8000 + 4989 + 10000)
    assert plan.race and plan.race.date == "2026-12-13"


def test_read_hourly_and_served_without_its_address(store):
    calls = []

    def handler(request):
        calls.append(str(request.url))
        return httpx.Response(200, text=FEED)

    plan = asyncio.run(runna.collect(CFG, store, datetime(2026, 10, 26, 8, tzinfo=UTC),
                                     transport=httpx.MockTransport(handler)))
    assert calls == [SECRET] and plan.sessions[0].name == "Threshold Intervals"

    main.app.state.store = store
    client = TestClient(main.app)
    assert client.get("/api/runs/plan").status_code == 503
    store.put_cache(runna.CACHE_KEY, plan.model_dump(mode="json"))
    served = client.get("/api/runs/plan")
    assert served.json()["race"]["name"] == "Half Marathon"
    assert "s3cret" not in served.text and "runna.example/w" not in served.text


@pytest.mark.parametrize("answer", [httpx.Response(404), httpx.ConnectError("no route to s3cret")])
def test_a_failing_feed_never_names_its_address(store, answer):
    def handler(request):
        if isinstance(answer, Exception):
            raise answer
        return answer

    with pytest.raises(RuntimeError) as failed:
        asyncio.run(runna.collect(CFG, store, transport=httpx.MockTransport(handler)))
    # Nothing in the log line names it: not the message, nor an error chained to it.
    assert "s3cret" not in str(failed.value)
    assert failed.value.__cause__ is None
    assert failed.value.__context__ is None or failed.value.__suppress_context__


def test_off_without_a_feed():
    assert not runna.settings({})["enabled"]
    assert not runna.settings({"running": {"runna_feed": "http://plain.example/x.ics"}})["enabled"]


def test_scheduled_hourly_only_with_a_feed(store):
    from app import scheduler

    def ids(cfg):
        built = scheduler.build(cfg | {"nas": {"docker_socket": "/x"}}, store)
        return {j.id for j in built.get_jobs()}

    assert "runna" in ids(CFG) and "runna" not in ids({})
