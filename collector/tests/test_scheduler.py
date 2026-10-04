from __future__ import annotations

import asyncio

from pydantic import BaseModel

from app import scheduler


class Payload(BaseModel):
    as_of: str
    stale: bool = False


def test_run_caches_a_successful_result(store):
    async def job():
        return Payload(as_of="2026-09-30T12:00:00Z")

    asyncio.run(scheduler._run(store, "nas", job))

    assert store.get_cache("nas") == {"as_of": "2026-09-30T12:00:00Z", "stale": False}


def test_failed_run_keeps_last_good_payload_flagged_stale(store):
    store.put_cache("nas", {"as_of": "2026-09-30T12:00:00Z", "stale": False})

    async def job():
        raise RuntimeError("node_exporter down")

    asyncio.run(scheduler._run(store, "nas", job))

    # as_of stays at the last good fetch, so the screen can say how old it is.
    assert store.get_cache("nas") == {"as_of": "2026-09-30T12:00:00Z", "stale": True}


def test_failed_run_with_nothing_cached_stays_empty(store):
    async def job():
        raise RuntimeError("down")

    asyncio.run(scheduler._run(store, "nas", job))

    assert store.get_cache("nas") is None


def mirror_cfg(mirror: bool) -> dict:
    return {"timezone": "Europe/Amsterdam", "nas": {"docker_socket": "/nope"},
            "github": {"owners": [{"login": "PimVanLeeuwen", "mirror": mirror}],
                       "mirror": {"at": "02:00"}}}


def test_the_github_mirror_runs_nightly_and_catches_up_after_startup(store):
    sched = scheduler.build(mirror_cfg(True), store)
    job = sched.get_job("github-mirror")

    assert "hour='2'" in str(job.trigger) and "minute='0'" in str(job.trigger)
    # Never run yet: it is overdue, so a run comes right after startup. (A job
    # added before start only has a next_run_time when one was given.)
    assert job.next_run_time is not None

    store.put_cache("github_mirror", {"next_due": "2999-01-01T00:00:00+00:00"})
    later = scheduler.build(mirror_cfg(True), store).get_job("github-mirror")
    assert not hasattr(later, "next_run_time")

    assert scheduler.build(mirror_cfg(False), store).get_job("github-mirror") is None
