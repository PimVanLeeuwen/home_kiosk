from __future__ import annotations

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from app import desk
from app.desk_briefing import briefing_screen

ZONE = ZoneInfo("Europe/Amsterdam")
MORNING = datetime(2026, 10, 29, 6, 15, tzinfo=UTC)  # 07:15 in Amsterdam
DIGEST = {
    "as_of": "2026-10-29T05:30:00+00:00", "stale": False, "date": "2026-10-29",
    "until": "2026-10-29T09:00:00+01:00",
    "line": "A quiet night — dry until 16:00, train on time.",
    "facts": ["Backup done 03:41", "Sonarr updated ✅", "Train on time, 4", "Stand-up 09:30"],
    "paragraph": "Good morning.",
}


def test_shows_the_line_and_facts_in_the_panel_fonts(store):
    store.put_cache("briefing", DIGEST)

    screen = briefing_screen(store, ZONE, MORNING)

    assert screen == {
        "kind": "briefing", "stale": False, "present": True,
        "title": "BRIEFING · THURSDAY",
        "line": "A quiet night - dry until 16:00, train on time.",
        "facts": ["Backup done 03:41", "Sonarr updated", "Train on time, 4", "Stand-up 09:30"],
        "as_of": "written by Claude at 06:30",
    }


def test_gone_at_nine_and_on_other_days(store):
    store.put_cache("briefing", DIGEST)

    assert not briefing_screen(store, ZONE, datetime(2026, 10, 29, 8, 0, tzinfo=UTC))["present"]
    assert not briefing_screen(store, ZONE, datetime(2026, 10, 30, 6, 15, tzinfo=UTC))["present"]
    assert briefing_screen(store, ZONE, MORNING)["present"]


def test_without_a_digest_there_is_no_screen(store):
    assert briefing_screen(store, ZONE, MORNING) == {"kind": "briefing", "stale": False,
                                                     "present": False}


def test_on_the_now_panel_right_after_the_clock(store):
    store.put_cache("briefing", DIGEST)

    kinds = [s["kind"] for s in desk.answer({"timezone": "Europe/Amsterdam"}, store, "now",
                                            MORNING)["screens"]]

    assert kinds[:5] == ["clock", "sky", "night", "briefing", "train"]  # after the skies
