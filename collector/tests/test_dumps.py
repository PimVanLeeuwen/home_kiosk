from __future__ import annotations

import asyncio
import json

from fastapi.testclient import TestClient

from app import main
from app.sources import db_copy, dumps


def run_line(day, **results):
    """One host job run; results maps a database to its error (None for success)."""
    return json.dumps({
        "started": f"2026-10-{day:02d}T02:30:00+0200",
        "finished": f"2026-10-{day:02d}T02:30:05+0200",
        "ok": not any(results.values()),
        "dumps": [
            {"name": name, "container": f"{name}-db", "ok": error is None,
             "exit": 1 if error else 0, "bytes": 0 if error else 1000 * day, "seconds": 1,
             "error": error}
            for name, error in results.items()
        ],
    })


def write_runs(tmp_path, *lines):
    path = tmp_path / "dump-runs.jsonl"
    path.write_text("\n".join(lines) + "\n")
    return str(path)


def test_each_database_shows_its_newest_attempt_and_last_success(tmp_path, store):
    path = write_runs(
        tmp_path,
        run_line(7, ghostfolio=None, tandoor=None),
        run_line(8, ghostfolio=None, tandoor='pg_dump: "db" refused'),
        "{half a line",
    )

    payload = dumps.read(path, store)

    ghostfolio, tandoor, hub = payload.databases
    assert (ghostfolio.label, ghostfolio.kind, ghostfolio.ok, ghostfolio.bytes) == (
        "Ghostfolio", "pg_dump", True, 8000)
    assert ghostfolio.last_success == ghostfolio.at
    assert (tandoor.ok, tandoor.bytes, tandoor.error) == (False, None, 'pg_dump: "db" refused')
    assert tandoor.last_success.day == 7
    assert [(r.ok, r.failed) for r in payload.runs] == [(False, 1), (True, 0)]
    # The hub copy has not run yet.
    assert (hub.name, hub.label, hub.kind, hub.ok) == ("hub", "Home hub", "sqlite", None)


def test_a_database_taken_out_of_the_job_is_no_longer_listed(tmp_path, store):
    path = write_runs(
        tmp_path,
        run_line(7, ghostfolio=None, tandoor=None),
        run_line(8, ghostfolio=None),
    )

    payload = dumps.read(path, store)

    assert [d.name for d in payload.databases] == ["ghostfolio", "hub"]
    # Its old runs still count in the history.
    assert [(r.ok, r.failed) for r in payload.runs] == [(True, 0), (True, 0)]


def test_no_run_file_yet_leaves_only_the_hub_copy(tmp_path, store):
    payload = dumps.read(str(tmp_path / "missing.jsonl"), store)

    assert [d.name for d in payload.databases] == ["hub"] and payload.runs == []


def test_the_hub_copy_keeps_its_last_success_after_a_failure(tmp_path, store):
    asyncio.run(main.scheduler._run(store, db_copy.CACHE_KEY, lambda: db_copy.collect(store)))
    first = store.get_cache(db_copy.CACHE_KEY)
    (store.path.parent / "backup" / store.path.name).unlink()
    (store.path.parent / "backup").rmdir()
    (store.path.parent / "backup").write_text("in the way")

    asyncio.run(main.scheduler._run(store, db_copy.CACHE_KEY, lambda: db_copy.collect(store)))

    (hub,) = dumps.read(str(tmp_path / "missing.jsonl"), store).databases
    assert hub.ok is False and hub.error
    assert hub.last_success.isoformat() == first["last_success"].replace("Z", "+00:00")


def test_the_endpoint_serves_the_cached_payload(store):
    main.app.state.store = store
    main.app.state.config = {}
    client = TestClient(main.app)

    assert client.get("/api/database-dumps").status_code == 503
    store.put_cache(dumps.CACHE_KEY, {"as_of": "2026-10-09T10:00:00Z", "stale": False})
    assert client.get("/api/database-dumps").json()["as_of"] == "2026-10-09T10:00:00Z"


def check_line(day, ok=True):
    return json.dumps({
        "started": f"2026-10-{day:02d}T05:00:00+0200",
        "finished": f"2026-10-{day:02d}T05:01:30+0200",
        "ok": ok,
        "checks": [{"name": "download:databases", "ok": True, "detail": "3 files, identical"},
                   {"name": "ghostfolio", "ok": ok,
                    "detail": "restored: 212 activities" if ok else "pg_restore failed"}],
    })


def test_restore_checks_newest_first_with_the_last_good_one(tmp_path, store):
    checks = tmp_path / "restore-checks.jsonl"
    checks.write_text("\n".join([check_line(1), "{broken", check_line(8, ok=False)]) + "\n")

    payload = dumps.read(str(tmp_path / "missing.jsonl"), store, str(checks))

    assert [(c.finished.day, c.ok) for c in payload.restore_checks] == [(8, False), (1, True)]
    assert payload.restore_checks[0].checks[1].detail == "pg_restore failed"
    assert payload.last_verified.day == 1


def test_no_restore_check_yet(tmp_path, store):
    payload = dumps.read(str(tmp_path / "missing.jsonl"), store, str(tmp_path / "none.jsonl"))

    assert payload.restore_checks == [] and payload.last_verified is None
