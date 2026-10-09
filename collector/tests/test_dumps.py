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
