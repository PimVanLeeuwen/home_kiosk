from __future__ import annotations

import json
from datetime import datetime

from fastapi.testclient import TestClient

from app import main
from app.sources import backups


def stats_line(bytes_, errors=0, last_error=None):
    stats = {"bytes": bytes_, "checks": 5120, "deletes": 3, "elapsedTime": 241.5,
             "errors": errors, "totalBytes": bytes_, "transfers": 118}
    if last_error:
        stats["lastError"] = last_error
    return {"time": "2026-10-02T03:03:00+02:00", "level": "info", "msg": "final", "stats": stats}


def run_line(day, ok=True, v3_exit=0, v1_stats=True):
    return json.dumps({
        "started": f"2026-09-{day:02d}T03:00:00+0200",
        "finished": f"2026-09-{day:02d}T03:23:00+0200",
        "ok": ok,
        "volumes": [
            {"name": "volume1", "exit": 0, "seconds": 241,
             "rclone": stats_line(2_468_000_000) if v1_stats else None},
            {"name": "volume3", "exit": v3_exit, "seconds": 1140,
             "rclone": stats_line(10, errors=1, last_error="quota exceeded") if v3_exit
             else stats_line(500_000_000)},
        ],
    })


def test_parse_line_reads_volumes_and_rclone_stats():
    run = backups.parse_line(run_line(28, ok=False, v3_exit=7))

    assert run.ok is False
    v1, v3 = run.volumes
    assert (v1.name, v1.ok, v1.seconds, v1.bytes, v1.transfers, v1.errors) == (
        "volume1", True, 241, 2_468_000_000, 118, 0)
    assert (v3.ok, v3.exit_code, v3.errors, v3.last_error) == (False, 7, 1, "quota exceeded")


def test_a_volume_without_stats_still_counts():
    v1 = backups.parse_line(run_line(28, v1_stats=False)).volumes[0]

    assert (v1.ok, v1.bytes, v1.transfers) == (True, None, None)


def test_read_sorts_newest_first_skips_bad_lines_and_tracks_last_success(tmp_path):
    path = tmp_path / "backup-runs.jsonl"
    path.write_text("\n".join([
        run_line(26),
        "{not json",
        run_line(28, ok=False, v3_exit=7),
        "",
        run_line(27),
        '{"started": "2026-09-29T03:00:00+0200"',  # half-written last line
    ]) + "\n")

    history = backups.read(str(path))

    assert [r.started.day for r in history.runs] == [28, 27, 26]
    by_name = {v.name: v for v in history.volumes}
    assert by_name["volume1"].last_success.day == 28
    # volume3 failed on the 28th; its last success was the 27th.
    assert by_name["volume3"].last_success.day == 27
    assert by_name["volume3"].last_run.started.day == 28
    # read() defaults to 03:00 UTC; the last run finished 01:23 UTC on the 28th.
    assert history.next_due.isoformat() == "2026-09-28T03:00:00+00:00"


def test_read_without_a_file_is_an_empty_history(tmp_path):
    history = backups.read(str(tmp_path / "missing.jsonl"))

    assert (history.runs, history.volumes, history.next_due) == ([], [], None)


def test_read_keeps_the_newest_runs_only(tmp_path):
    path = tmp_path / "backup-runs.jsonl"
    lines = [run_line(1 + i % 28).replace("2026-09", f"2026-{1 + i // 28:02d}")
             for i in range(120)]
    path.write_text("\n".join(lines))

    assert len(backups.read(str(path)).runs) == backups.MAX_RUNS


def test_backups_endpoint(store):
    main.app.state.store = store
    client = TestClient(main.app)
    assert client.get("/api/backups").status_code == 503

    store.put_cache("backups", {"as_of": "2026-10-01T12:00:00+00:00", "stale": False,
                                "runs": [], "volumes": [], "next_due": None})
    assert client.get("/api/backups").json()["runs"] == []


def test_a_retried_error_on_a_good_volume_is_not_shown():
    line = json.loads(run_line(28))
    line["volumes"][0]["rclone"]["stats"]["lastError"] = "temporary hiccup"
    v1 = backups.parse_line(json.dumps(line)).volumes[0]

    assert (v1.ok, v1.errors, v1.last_error) == (True, 0, None)


def test_next_run_is_the_next_scheduled_start_in_local_time():
    def nxt(iso, at="03:00"):
        return backups.next_run(datetime.fromisoformat(iso), at, "Europe/Amsterdam").isoformat()

    # Finished at 03:23 local: next is tomorrow 03:00.
    assert nxt("2026-09-28T03:23:00+02:00") == "2026-09-29T03:00:00+02:00"
    # A late manual run in the evening: still the coming night.
    assert nxt("2026-09-28T20:33:00+02:00") == "2026-09-29T03:00:00+02:00"
    # Finished before the scheduled time (e.g. a manual run at 01:00): same night.
    assert nxt("2026-09-29T01:00:00+02:00") == "2026-09-29T03:00:00+02:00"
    # Across the switch to winter time (last Sunday of October).
    assert nxt("2026-10-24T03:20:00+02:00") == "2026-10-25T03:00:00+01:00"
