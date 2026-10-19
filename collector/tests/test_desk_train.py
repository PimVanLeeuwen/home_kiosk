from __future__ import annotations

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from app.desk_train import train_screen
from app.models import Train, TrainDisruption, TrainRun, TrainStop

AMS = ZoneInfo("Europe/Amsterdam")
DAY = "2026-10-14"  # a Wednesday


def at(h: int, m: int, day: int = 14) -> datetime:
    return datetime(2026, 10, day, h, m, tzinfo=AMS)


def stops(late: int = 0, skip: str = "") -> list[TrainStop]:
    times = [(7, 16, "Leiden Centraal", "3"), (7, 36, "Den Haag HS", None),
             (8, 5, "Delft", None), (8, 41, "Rotterdam Centraal", None)]
    return [TrainStop(name=n, planned=at(h, m), actual=at(h, m) + timedelta(minutes=late),
                      track=t, cancelled=n == skip) for h, m, n, t in times]


def run(status="on_time", late=0, track="3", was=None, skip="", planned=(7, 16)) -> TrainRun:
    leaves = at(*planned)
    return TrainRun(name="IC 3522", status=status, planned_departure=leaves,
                    actual_departure=leaves + timedelta(minutes=late), delay_minutes=late,
                    planned_track=was or track, actual_track=track, stops=stops(late, skip))


def put(store, mode="morning", watching=True, date=DAY, **fields) -> None:
    train = Train(as_of=datetime.now(UTC), date=date,
                  route="Leiden Centraal to Rotterdam Centraal", departure="07:16",
                  mode=mode, watching=watching, departed=False, **fields)
    store.put_cache("train", train.model_dump(mode="json"))


def screen(store, now: datetime) -> dict:
    return train_screen(store, AMS, now.astimezone(UTC))


def test_hidden_without_a_train_to_follow(store):
    assert screen(store, at(7, 0)) == {"kind": "train", "stale": False, "present": False}
    put(store, mode="idle", watching=False, train=None)
    assert screen(store, at(12, 0))["present"] is False
    put(store, watching=False, train=run())  # it has left
    assert screen(store, at(7, 20))["present"] is False
    put(store, date="2026-10-13", train=run())  # yesterday's, kept overnight
    assert screen(store, at(6, 30))["present"] is False


def test_on_time_counts_down_from_its_platform(store):
    put(store, train=run())
    s = screen(store, at(6, 42))
    assert s["present"] and s["title"] == "Your train · direct"
    assert (s["status"], s["tone"], s["departure"]) == ("On time", "up", "07:16")
    assert s["departure_now"] is None
    assert (s["platform"], s["platform_was"], s["sub"]) == ("3", None, "")
    assert s["leaves_at"] == round(at(7, 16).timestamp()) and s["ring_label"] == "min to go"
    assert [x["time"] for x in s["stops"]] == ["07:16", "07:36", "08:05", "08:41"]
    assert s["gone"] is False and s["next"] is None and s["notice"] is None


def test_late_shows_the_new_time_and_a_changed_platform(store):
    put(store, train=run(status="late", late=6, track="4", was="3"))
    s = screen(store, at(7, 0))
    assert (s["status"], s["tone"], s["departure_now"]) == ("6 min late", "warn", "07:22")
    assert (s["platform"], s["platform_was"]) == ("4", "3")
    assert s["leaves_at"] == round(at(7, 22).timestamp())
    assert s["stops"][1] == {"time": "07:42", "name": "Den Haag HS", "shifted": True,
                             "cancelled": False}


def test_cancelled_points_at_the_next_direct_train(store):
    put(store, train=run(status="cancelled"), next_direct=run(planned=(7, 46), track="4"))
    s = screen(store, at(7, 0))
    assert (s["status"], s["tone"], s["gone"]) == ("Cancelled", "down", True)
    assert s["sub"] == "The 07:16 to Rotterdam Centraal does not run"
    assert s["platform"] is None and s["ring_label"] == "min to next"
    assert s["leaves_at"] == round(at(7, 46).timestamp())
    assert s["next"] == {"departure": "07:46", "platform": "4", "arrives": "08:41"}
    assert all(not x["shifted"] for x in s["stops"])


def test_the_evening_before_only_with_a_problem(store):
    disruption = TrainDisruption(id="d1", kind="MAINTENANCE", title="Utrecht - Amsterdam.",
                                 text="minder treinen", until="Tot zondag.")
    put(store, mode="evening", date="2026-10-15", train=run(skip="Delft"),
        disruptions=[disruption])
    s = screen(store, at(20, 5))
    assert s["title"] == "Tomorrow's train · direct"
    assert (s["status"], s["tone"]) == ("Skips Delft", "warn")
    assert s["sub"] == "Tomorrow at 07:16 from platform" and s["platform"] == "3"
    assert s["leaves_at"] is None and s["stops"][2]["cancelled"] is True
    assert s["notice"] == {"title": "Utrecht - Amsterdam.",
                           "text": "minder treinen Tot zondag. (NS)"}


def test_a_train_nss_planner_lost(store):
    put(store, train=run(status="not_found"))
    s = screen(store, at(7, 0))
    assert (s["status"], s["tone"]) == ("Not in NS's planner", "down")
    assert s["gone"] is True and s["leaves_at"] is None


def test_text_is_kept_to_what_the_panel_fonts_hold():
    from app.desk_train import latin1
    text = "Utrecht \u2013 Amsterdam \u2018werk\u2019\u2026 caf\u00e9"
    assert latin1(text) == "Utrecht - Amsterdam 'werk'... caf\u00e9"
    assert latin1("\u2192 Zwolle") == "? Zwolle"
