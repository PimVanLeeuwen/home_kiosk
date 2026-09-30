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
