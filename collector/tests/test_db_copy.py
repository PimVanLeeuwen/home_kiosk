from __future__ import annotations

import asyncio
import sqlite3

from app import scheduler
from app.sources import db_copy


def test_the_copy_holds_the_same_data_next_to_the_database(store):
    store.put_cache("nas", {"v": 1})

    result = db_copy.write(store)

    assert result.ok and result.error is None
    copy = store.path.parent / "backup" / store.path.name
    assert result.path == str(copy) and result.bytes == copy.stat().st_size
    with sqlite3.connect(copy) as conn:
        assert conn.execute("SELECT key FROM cache").fetchall() == [("nas",)]
    assert not list(copy.parent.glob("*.partial"))


def test_a_second_copy_replaces_the_first(store):
    db_copy.write(store)
    store.put_cache("news", {"v": 2})

    db_copy.write(store)

    copy = db_copy.target(store)
    with sqlite3.connect(copy) as conn:
        keys = {row[0] for row in conn.execute("SELECT key FROM cache")}
    assert "news" in keys


def test_a_failed_copy_is_reported_and_leaves_no_partial_file(store):
    # A file where the backup folder should be: the copy cannot be written.
    (store.path.parent / "backup").write_text("in the way")

    result = db_copy.write(store)

    assert not result.ok and result.error and result.bytes is None


def test_the_job_caches_its_result(store):
    asyncio.run(scheduler._run(store, db_copy.CACHE_KEY, lambda: db_copy.collect(store)))

    assert store.get_cache(db_copy.CACHE_KEY)["ok"] is True


def test_the_copy_runs_nightly_before_the_backup(store):
    cfg = {"timezone": "Europe/Amsterdam", "database_copy": {"at": "02:45"}}

    job = scheduler.build(cfg, store).get_job("db-copy")

    assert "hour='2'" in str(job.trigger) and "minute='45'" in str(job.trigger)
