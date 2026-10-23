from __future__ import annotations

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from app import desk_backups, desk_nas
from app.alerts import rules

ZONE = ZoneInfo("Europe/Amsterdam")
NOW = datetime(2026, 10, 22, 18, 0, tzinfo=UTC)  # Thursday 20:00 in Amsterdam


def pool(name, used_pct, total=6e12, **extra):
    return {"name": name, "used_bytes": int(total * used_pct / 100), "total_bytes": int(total),
            "used_pct": used_pct, "free_bytes": int(total * (100 - used_pct) / 100)} | extra


def put_nas(store, *pools, disks=("ok", "ok", "ok", "ok"), ups="online", stale=False):
    store.put_cache("nas", {"as_of": NOW.isoformat(), "stale": stale,
                            "storage": {"pools": list(pools)}, "cpu_pct": 12.4, "ram_pct": 41.2,
                            "disks": [{"name": f"sd{i}", "smart": s} for i, s in enumerate(disks)]})
    store.put_cache("ups", {"as_of": NOW.isoformat(), "stale": False, "status": ups})


def incident(store, key, rule, severity="warning"):
    with store.connect() as conn:
        conn.execute("INSERT INTO alert_incident (key, rule, severity, title, opened_at, "
                     "last_seen_at) VALUES (?, ?, ?, ?, ?, ?)",
                     (key, rule, severity, key, NOW.isoformat(), NOW.isoformat()))


# --- NAS -------------------------------------------------------------------------------


def test_the_fullest_pool_with_its_alert_mark_and_runway(store):
    put_nas(store, pool("volume1", 39.4, projection_months=18.7),
            pool("volume2", 88.2, total=17.9e12, projection_months=5.2))
    s = desk_nas.nas_screen(store, ZONE, NOW)
    assert (s["kind"], s["present"], s["status"], s["warn"]) == ("nas", True, "HEALTHY", False)
    assert (s["pool"], s["used_pct"], s["limit_pct"]) == (
        "volume2", 88, rules.DEFAULT_RULES["disk_space"]["threshold_pct"])
    assert s["size"] == "volume2 · 15.8 TB of 17.9 TB"
    assert s["runway"] == "full in about 5 months"
    assert (s["cpu"], s["ram"], s["disks"], s["disks_line"], s["ups"]) == (
        12, 41, [True] * 4, "4 of 4", "UPS ok")


def test_open_nas_alerts_a_failing_disk_and_the_ups_on_battery(store):
    put_nas(store, pool("volume1", 82.1), disks=("ok", "failing", "ok"), ups="on_battery")
    incident(store, "smart:sd1", "smart", "error")
    incident(store, "train:x", "train")  # not about the NAS
    s = desk_nas.nas_screen(store, ZONE, NOW)
    assert (s["status"], s["warn"], s["runway"]) == ("1 ISSUE", True, "")
    assert (s["disks"], s["disks_line"]) == ([True, False, True], "2 of 3")
    assert (s["ups"], s["ups_ok"]) == ("UPS on battery", False)


def test_sparklines_are_the_day_in_at_most_24_points(store):
    put_nas(store, pool("volume1", 50))
    for i in range(144):  # every 10 minutes over the last day
        store.put_nas_sample(NOW - timedelta(minutes=10 * (143 - i)), 0, 0, float(i % 50), 40.0,
                             50.0)
    s = desk_nas.nas_screen(store, ZONE, NOW)
    assert 0 < len(s["cpu_points"]) <= desk_nas.POINTS and set(s["ram_points"]) == {40}


def test_runway_words():
    assert [desk_nas.runway(m) for m in (None, .4, 1.2, 30)] == [
        "", "full within a month", "full in about 1 month", "full in about 2 years"]


def test_no_nas_read_yet(store):
    assert desk_nas.nas_screen(store, ZONE, NOW) == {
        "kind": "nas", "stale": False, "present": False}


# --- backups ---------------------------------------------------------------------------


def run(day, start="01:00", minutes=70, ok=True, gb=4.1):
    started = datetime.fromisoformat(f"2026-10-{day:02d}T{start}:00+00:00")
    return {"started": started.isoformat(),
            "finished": (started + timedelta(minutes=minutes)).isoformat(), "ok": ok,
            "volumes": [{"name": "volume1", "bytes": int(gb * 1e9)}]}


def put_backups(store, runs, restore=None):
    store.put_cache("backups", {"as_of": NOW.isoformat(), "stale": False, "runs": runs,
                                "storage_box": {"used_pct": 21.7}})
    if restore is not None:
        store.put_cache("dumps", {"as_of": NOW.isoformat(), "stale": False,
                                  "restore_checks": restore})


def test_last_night_the_restore_check_and_the_nights(store):
    runs = [run(d) for d in range(1, 23)]
    runs[15] = run(16, minutes=110)  # a slow night
    runs[18] = run(19, ok=False)
    runs.append(run(22, start="16:29", minutes=3, gb=.2))  # a run by hand this evening
    put_backups(store, runs, restore=[{"started": "2026-10-10T01:00:00+00:00",
                                       "finished": "2026-10-10T01:30:00+00:00", "ok": True}])
    s = desk_backups.backups_screen(store, ZONE, NOW)
    assert (s["kind"], s["status"], s["ok"], s["box"]) == (
        "backups", "ALL SAFE", True, "Storage Box · 22% used")
    assert (s["time"], s["line"]) == ("18:29", "Today · 3 min · 200 MB")
    assert s["restore"] == "Restore verified 12 days ago" and s["restore_tone"] == "ok"
    nights = s["nights"]
    assert len(nights) == 22 and nights[-1] == {"seconds": 180, "state": "ok"}
    assert nights[15]["state"] == "slow" and nights[18]["state"] == "failed"


def test_a_failed_restore_check_and_open_backup_alerts(store):
    put_backups(store, [run(21)], restore=[{"started": "2026-10-09T08:00:00+00:00",
                                            "finished": "2026-10-09T08:58:00+00:00",
                                            "ok": False}])
    incident(store, "backup_missing:restore-check", "backup_missing", "error")
    s = desk_backups.backups_screen(store, ZONE, NOW)
    assert (s["status"], s["warn"]) == ("1 PROBLEM", True)
    assert (s["restore"], s["restore_tone"]) == ("Restore check failed on 9 Oct", "failed")
    assert s["line"] == "Yesterday · 1 h 10 min · 4 GB"


def test_a_run_is_named_by_when_it_started():
    now = datetime(2026, 10, 22, 20, 0)
    at = [datetime(2026, 10, 22, 7), datetime(2026, 10, 22, 3), datetime(2026, 10, 21, 23),
          datetime(2026, 10, 21, 9), datetime(2026, 10, 19, 3)]
    assert [desk_backups._when(t, now) for t in at] == [
        "Today", "Last night", "Last night", "Yesterday", "19 Oct"]


def test_no_restore_check_yet_and_no_runs_yet(store):
    put_backups(store, [run(21)])
    assert desk_backups.backups_screen(store, ZONE, NOW)["restore_tone"] == "none"
    put_backups(store, [])
    assert desk_backups.backups_screen(store, ZONE, NOW)["present"] is False
