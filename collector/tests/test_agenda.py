from __future__ import annotations

import asyncio
from datetime import UTC, date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx
import pytest
from fastapi.testclient import TestClient

from app import main
from app.sources import agenda

AMS = ZoneInfo("Europe/Amsterdam")
CFG = {"timezone": "Europe/Amsterdam",
       "calendar": {"username": "me@example.com", "app_password": "abcd-efgh-ijkl-mnop"}}
NOW = datetime(2026, 10, 14, 7, 0, tzinfo=UTC)  # 09:00 in Amsterdam, a Wednesday
HOLIDAYS = (Path(__file__).parent / "fixtures" / "nl_holidays.ics").read_text()
FEED = "https://feeds.example.com/private/abc123token.ics"

# The calendar list as iCloud shows it: own calendars, a subscription, a task
# list and the inbox (the last two are left out).
LIST = f"""<?xml version="1.0"?>
<d:multistatus xmlns:d="DAV:" xmlns:c="urn:ietf:params:xml:ns:caldav"
 xmlns:cs="http://calendarserver.org/ns/" xmlns:a="http://apple.com/ns/ical/">
 <d:response><d:href>/123/calendars/work-id/</d:href><d:propstat><d:prop>
  <d:displayname>Work</d:displayname><a:calendar-color>#FF8D28FF</a:calendar-color>
  <d:resourcetype><d:collection/><c:calendar/></d:resourcetype>
  <c:supported-calendar-component-set><c:comp name="VEVENT"/></c:supported-calendar-component-set>
 </d:prop></d:propstat></d:response>
 <d:response><d:href>/123/calendars/shared-id/</d:href><d:propstat><d:prop>
  <d:displayname>Pim en Sanne </d:displayname><a:calendar-color>#FF383CFF</a:calendar-color>
  <d:resourcetype><d:collection/><c:calendar/><cs:shared-owner/></d:resourcetype>
  <c:supported-calendar-component-set><c:comp name="VEVENT"/></c:supported-calendar-component-set>
 </d:prop></d:propstat></d:response>
 <d:response><d:href>/123/calendars/holidays-id/</d:href><d:propstat><d:prop>
  <d:displayname>Nederlandse feestdagen</d:displayname>
  <a:calendar-color>#FFCC00FF</a:calendar-color>
  <d:resourcetype><d:collection/><cs:subscribed/></d:resourcetype>
  <cs:source><d:href>{FEED.replace("https://", "webcal://")}</d:href></cs:source>
 </d:prop></d:propstat></d:response>
 <d:response><d:href>/123/calendars/tasks-id/</d:href><d:propstat><d:prop>
  <d:displayname>Reminders</d:displayname>
  <d:resourcetype><d:collection/><c:calendar/></d:resourcetype>
  <c:supported-calendar-component-set><c:comp name="VTODO"/></c:supported-calendar-component-set>
 </d:prop></d:propstat></d:response>
 <d:response><d:href>/123/calendars/inbox/</d:href><d:propstat><d:prop>
  <d:resourcetype><d:collection/><c:schedule-inbox/></d:resourcetype>
 </d:prop></d:propstat></d:response>
</d:multistatus>"""

# A weekly standup (moved today: 09:30 instead of 09:00), a dinner, a birthday.
WORK = """BEGIN:VCALENDAR
VERSION:2.0
BEGIN:VEVENT
UID:standup
DTSTART;TZID=Europe/Amsterdam:20260902T090000
DTEND;TZID=Europe/Amsterdam:20260902T091500
RRULE:FREQ=WEEKLY;BYDAY=WE
SUMMARY:Standup
END:VEVENT
BEGIN:VEVENT
UID:standup
RECURRENCE-ID;TZID=Europe/Amsterdam:20261014T090000
DTSTART;TZID=Europe/Amsterdam:20261014T093000
DTEND;TZID=Europe/Amsterdam:20261014T094500
SUMMARY:Standup (moved)
END:VEVENT
END:VCALENDAR
"""
SHARED = """BEGIN:VCALENDAR
VERSION:2.0
BEGIN:VEVENT
UID:dinner
DTSTART:20261014T170000Z
DTEND:20261014T191500Z
SUMMARY:Dinner
END:VEVENT
BEGIN:VEVENT
UID:bday
DTSTART;VALUE=DATE:20261014
DTEND;VALUE=DATE:20261015
SUMMARY:Mama's birthday
END:VEVENT
END:VCALENDAR
"""


def report(ics: str) -> str:
    body = ics.replace("&", "&amp;").replace("<", "&lt;")
    return ('<?xml version="1.0"?><d:multistatus xmlns:d="DAV:" '
            'xmlns:c="urn:ietf:params:xml:ns:caldav"><d:response><d:href>/x.ics</d:href>'
            f'<d:propstat><d:prop><c:calendar-data>{body}</c:calendar-data></d:prop>'
            '</d:propstat></d:response></d:multistatus>')


PRINCIPAL = ('<d:multistatus xmlns:d="DAV:"><d:response><d:propstat><d:prop>'
             '<d:current-user-principal><d:href>/123/principal/</d:href>'
             '</d:current-user-principal></d:prop></d:propstat></d:response></d:multistatus>')
HOME = ('<d:multistatus xmlns:d="DAV:" xmlns:c="urn:ietf:params:xml:ns:caldav"><d:response>'
        '<d:propstat><d:prop><c:calendar-home-set>'
        '<d:href>https://p01-caldav.icloud.com/123/calendars/</d:href>'
        '</c:calendar-home-set></d:prop></d:propstat></d:response></d:multistatus>')


class ICloud:
    """A fake iCloud CalDAV server and the holiday feed's host."""

    def __init__(self, login_ok: bool = True, shared_down: bool = False):
        self.login_ok, self.shared_down, self.seen = login_ok, shared_down, []

    def transport(self) -> httpx.MockTransport:
        def handler(request: httpx.Request) -> httpx.Response:
            self.seen.append((request.method, request.url.host, request.url.path,
                              "authorization" in request.headers))
            if request.url.host == "feeds.example.com":
                return httpx.Response(200, text=HOLIDAYS)
            if not self.login_ok:
                return httpx.Response(401)
            path, method = request.url.path, request.method
            if method == "PROPFIND" and path == "/":
                return httpx.Response(207, text=PRINCIPAL)
            if method == "PROPFIND" and path == "/123/principal/":
                return httpx.Response(207, text=HOME)
            if method == "PROPFIND":
                return httpx.Response(207, text=LIST)
            if path.endswith("/work-id/"):
                return httpx.Response(207, text=report(WORK))
            if path.endswith("/shared-id/"):
                if self.shared_down:
                    return httpx.Response(503)
                return httpx.Response(207, text=report(SHARED))
            return httpx.Response(404)

        return httpx.MockTransport(handler)


@pytest.fixture
def cal_store(store):
    agenda.ensure_tables(store)
    return store


def collect(store, cloud: ICloud, now: datetime = NOW,
            reader: agenda.Reader | None = None) -> agenda.Today:
    reader = reader or agenda.Reader(transport=cloud.transport())
    return asyncio.run(agenda.collect(CFG, store, now=now, reader=reader))


def test_lists_own_calendars_and_subscriptions_without_task_lists(cal_store):
    reader = agenda.Reader(transport=ICloud().transport())
    collect(cal_store, ICloud(), reader=reader)

    listed = agenda.calendar_list(cal_store, reader)
    assert [(c.name, c.kind, c.color) for c in listed] == [
        ("Work", "icloud", "#ff8d28"), ("Pim en Sanne", "icloud", "#ff383c"),
        ("Nederlandse feestdagen", "subscribed", "#ffcc00")]
    # The subscription's address (with its token) is never in what Settings gets.
    assert "abc123token" not in str([c.model_dump() for c in listed])


def test_todays_events_with_a_moved_repeat_and_an_all_day_one(cal_store):
    today = collect(cal_store, ICloud())

    assert today.date == "2026-10-14"
    assert [(e.title, e.start.strftime("%H:%M"), e.end.strftime("%H:%M"), e.calendar)
            for e in today.events] == [
        ("Standup (moved)", "09:30", "09:45", "Work"),
        ("Dinner", "19:00", "21:15", "Pim en Sanne")]
    assert [(e.title, e.calendar) for e in today.all_day] == [("Mama's birthday", "Pim en Sanne")]


def test_subscriptions_are_read_from_their_feed_without_the_icloud_login(cal_store):
    cloud = ICloud()
    reader = agenda.Reader(transport=cloud.transport())
    christmas = datetime(2026, 12, 25, 8, 0, tzinfo=UTC)

    today = collect(cal_store, cloud, now=christmas, reader=reader)

    assert ("Eerste kerstdag", "Nederlandse feestdagen") in [(e.title, e.calendar)
                                                              for e in today.all_day]
    feed_calls = [s for s in cloud.seen if s[1] == "feeds.example.com"]
    assert feed_calls == [("GET", "feeds.example.com", "/private/abc123token.ics", False)]


def test_feeds_are_fetched_at_most_every_15_minutes(cal_store):
    cloud = ICloud()
    reader = agenda.Reader(transport=cloud.transport())
    collect(cal_store, cloud, reader=reader)
    collect(cal_store, cloud, now=datetime(2026, 10, 14, 7, 5, tzinfo=UTC), reader=reader)
    collect(cal_store, cloud, now=datetime(2026, 10, 14, 7, 20, tzinfo=UTC), reader=reader)

    assert len([s for s in cloud.seen if s[1] == "feeds.example.com"]) == 2
    # The calendar list too: once, not every run.
    assert len([s for s in cloud.seen if s[0] == "PROPFIND" and s[2] == "/"]) == 1


def test_a_hidden_calendar_is_not_read(cal_store):
    agenda.set_shown(cal_store, "shared-id", False)

    today = collect(cal_store, ICloud())

    assert {e.calendar for e in today.events + today.all_day} == {"Work"}
    agenda.set_shown(cal_store, "shared-id", True)
    assert agenda.hidden(cal_store) == set()


def test_one_calendar_failing_leaves_the_others(cal_store):
    today = collect(cal_store, ICloud(shared_down=True))

    assert today.errors == {"Pim en Sanne": "HTTP 503"}
    assert [e.title for e in today.events] == ["Standup (moved)"]


def test_a_refused_login_raises_so_the_last_answer_goes_stale(cal_store):
    with pytest.raises(httpx.HTTPStatusError):
        collect(cal_store, ICloud(login_ok=False))


def test_switched_off_without_a_password():
    assert agenda.settings(CFG)["enabled"] is True
    assert agenda.settings({"calendar": {"username": "me@example.com"}})["enabled"] is False


def test_settings_routes_list_and_switch_calendars(cal_store, monkeypatch):
    reader = agenda.Reader(transport=ICloud().transport())
    collect(cal_store, ICloud(), reader=reader)
    monkeypatch.setattr(agenda, "READER", reader)
    # No `with`: the lifespan would start the scheduler and hit real sources.
    main.app.state.store = cal_store
    main.app.state.config = CFG
    client = TestClient(main.app)
    origin = {"Origin": "http://testserver", "Content-Type": "application/json"}

    listed = client.get("/api/settings/calendars").json()
    switched = client.put("/api/settings/calendars/shared-id", json={"shown": False},
                          headers=origin).json()

    assert [c["name"] for c in listed] == ["Work", "Pim en Sanne", "Nederlandse feestdagen"]
    assert {c["id"]: c["shown"] for c in switched}["shared-id"] is False
    assert client.put("/api/settings/calendars/nope", json={"shown": False},
                      headers=origin).status_code == 404
    assert client.get("/api/calendar").status_code == 503  # nothing collected by the job yet


def test_floating_times_count_as_local():
    cal = agenda.icalendar.Calendar.from_ical(
        "BEGIN:VCALENDAR\nBEGIN:VEVENT\nUID:x\nDTSTART:20261014T120000\n"
        "DTEND:20261014T130000\nSUMMARY:Lunch\nEND:VEVENT\nEND:VCALENDAR\n")
    info = agenda.CalendarInfo(id="x", name="X", color="#000000", kind="icloud")

    (lunch,) = agenda.events_today([cal], info, date(2026, 10, 14), AMS)

    assert lunch.start == datetime(2026, 10, 14, 12, 0, tzinfo=AMS)
