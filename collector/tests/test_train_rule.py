from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime

import httpx
import pytest

from app.alerts import core, rules
from app.alerts.telegram import Telegram

SETTINGS = {"enabled": True, "late_minutes": 3}
CFG = {
    "timezone": "Europe/Amsterdam",
    "telegram": {"token": "t", "chats": {"nas": {"id": "-1", "label": "NAS"}}},
}
STOPS = [
    {"name": "Leiden Centraal", "planned": "2026-10-14T07:16:00+02:00", "actual": None,
     "track": "6", "cancelled": False},
    {"name": "Delft", "planned": "2026-10-14T08:11:00+02:00", "actual": None,
     "track": "7", "cancelled": False},
    {"name": "Rotterdam Centraal", "planned": "2026-10-14T08:28:00+02:00", "actual": None,
     "track": "2", "cancelled": False},
]


def run(**fields) -> dict:
    return {"name": "IC 3522", "status": "on_time",
            "planned_departure": "2026-10-14T07:16:00+02:00",
            "actual_departure": "2026-10-14T07:16:00+02:00", "delay_minutes": 0,
            "planned_track": "6", "actual_track": "6", "stops": STOPS} | fields


def payload(mode: str = "morning", **fields) -> dict:
    return {"as_of": "2026-10-14T05:00:00+00:00", "stale": False, "date": "2026-10-14",
            "route": "Leiden Centraal to Rotterdam Centraal", "departure": "07:16",
            "mode": mode, "watching": True, "departed": False, "train": run(),
            "next_direct": None, "disruptions": []} | fields


def titles(problems) -> list[str]:
    return [p.title for p in problems]


def test_on_time_is_quiet_and_idle_judges_nothing():
    assert rules.train(payload(), SETTINGS) == []
    assert rules.train(payload("idle"), SETTINGS) is None
    assert rules.train(None, SETTINGS) is None


def test_a_departed_train_closes_its_problems():
    assert rules.train(payload(departed=True, train=run(delay_minutes=12)), SETTINGS) == []


def test_late_from_three_minutes_and_again_when_clearly_worse():
    assert rules.train(payload(train=run(delay_minutes=2)), SETTINGS) == []

    six = rules.train(payload(train=run(status="late", delay_minutes=6,
                                        actual_departure="2026-10-14T07:22:00+02:00")), SETTINGS)
    twelve = rules.train(payload(train=run(status="late", delay_minutes=12)), SETTINGS)

    assert [p.key for p in six] == ["train:2026-10-14:late:3"]
    assert titles(six) == ["The 07:16 is 6 min late"]
    assert six[0].body == "IC 3522 now leaves at 07:22 from track 6."
    assert [p.key for p in twelve] == ["train:2026-10-14:late:10"]


def test_a_track_change():
    problems = rules.train(payload(train=run(actual_track="4")), SETTINGS)

    assert titles(problems) == ["The 07:16 leaves from track 4"]
    assert problems[0].body == "Not track 6."


def test_cancelled_names_the_next_direct_train():
    nxt = run(planned_departure="2026-10-14T07:46:00+02:00",
              stops=[STOPS[0], STOPS[1], STOPS[2] | {"planned": "2026-10-14T08:58:00+02:00"}])

    problems = rules.train(payload(train=run(status="cancelled"), next_direct=nxt), SETTINGS)

    assert titles(problems) == ["Today: the 07:16 does not run"]
    assert problems[0].body == ("IC 3522 is cancelled. "
                                "Next direct train: 07:46 from track 6, arrives 08:58.")


def test_the_evening_before_says_tomorrow_and_ignores_delays_and_tracks():
    problems = rules.train(payload("evening", train=None), SETTINGS)
    calm = rules.train(payload("evening", train=run(delay_minutes=9, actual_track="4")), SETTINGS)

    assert titles(problems) == ["Tomorrow: the 07:16 is not in NS's planner"]
    assert "No direct train found after it." in problems[0].body
    assert calm == []


def test_skipped_stops_and_works_on_the_route():
    stops = [STOPS[0], STOPS[1], STOPS[2] | {"cancelled": True}]
    works = {"id": "w1", "kind": "MAINTENANCE", "title": "Utrecht - Amsterdam.",
             "text": "Door werkzaamheden rijden er minder treinen.",
             "until": "Dit duurt tot ongeveer 10:00 uur."}

    problems = rules.train(payload("evening", train=run(stops=stops), disruptions=[works]),
                           SETTINGS)

    assert titles(problems) == [
        "Tomorrow: the 07:16 does not stop at Rotterdam Centraal",
        "Tomorrow, on your route: Utrecht - Amsterdam."]
    assert problems[1].body == ("Door werkzaamheden rijden er minder treinen.\n"
                                "Dit duurt tot ongeveer 10:00 uur.")


# --- sending -----------------------------------------------------------------


class Sent:
    def __init__(self):
        self.texts: list[str] = []

    def client(self) -> Telegram:
        def handler(request):
            self.texts.append(json.loads(request.content)["text"])
            return httpx.Response(200, json={"ok": True, "result": {}})

        return Telegram("t", transport=httpx.MockTransport(handler))


@pytest.fixture
def rule_store(store):
    core.ensure_tables(store)
    rules.ensure_tables(store)
    return store


def apply(store, judged, now: datetime, sent: Sent) -> None:
    asyncio.run(rules.apply(store, CFG, {"train": judged}, now, telegram=sent.client()))


def test_sent_in_quiet_hours_to_the_train_category(rule_store):
    sent = Sent()
    six_thirty = datetime(2026, 10, 14, 4, 30, tzinfo=UTC)  # 06:30 local, quiet until 07:00

    apply(rule_store, rules.train(payload(train=run(status="cancelled")), SETTINGS),
          six_thirty, sent)

    assert len(sent.texts) == 1
    message = core.messages(rule_store)[0]
    assert (message.category, message.status) == ("train", "sent")


def test_the_evening_message_is_not_repeated_the_next_morning(rule_store):
    sent = Sent()
    cancelled = run(status="cancelled")

    apply(rule_store, rules.train(payload("evening", train=cancelled), SETTINGS),
          datetime(2026, 10, 13, 18, 1, tzinfo=UTC), sent)
    apply(rule_store, rules.train(payload("idle"), SETTINGS),
          datetime(2026, 10, 13, 23, 0, tzinfo=UTC), sent)
    apply(rule_store, rules.train(payload(train=cancelled), SETTINGS),
          datetime(2026, 10, 14, 4, 0, tzinfo=UTC), sent)

    assert len(sent.texts) == 1
    assert "Tomorrow: the 07:16 does not run" in sent.texts[0]


def test_no_resolved_message_when_the_train_has_left(rule_store):
    sent = Sent()

    apply(rule_store, rules.train(payload(train=run(status="late", delay_minutes=6)), SETTINGS),
          datetime(2026, 10, 14, 5, 0, tzinfo=UTC), sent)
    apply(rule_store, rules.train(payload(departed=True), SETTINGS),
          datetime(2026, 10, 14, 5, 30, tzinfo=UTC), sent)

    assert len(sent.texts) == 1
