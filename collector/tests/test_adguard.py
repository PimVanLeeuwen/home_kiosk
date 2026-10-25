from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

import httpx
import pytest

from app.sources import adguard

CFG = {"adguard": {"url": "http://nas:8053/", "user": "hub", "password": "pw"}}
NOW = datetime(2026, 10, 25, 14, 0, tzinfo=UTC)

# Trimmed from a running AdGuard v0.107.79.
STATS = {
    "time_units": "hours",
    "top_clients": [{"192.168.1.20": 800}],
    "top_blocked_domains": [{"doubleclick.net": 31}, {"app-measurement.com": 12}],
    "dns_queries": [10] * 23 + [570],
    "blocked_filtering": [1] * 23 + [73],
    "num_dns_queries": 800,
    "num_blocked_filtering": 96,
}
STATUS = {"version": "v0.107.79", "protection_enabled": True, "running": True}


def answer(stats=STATS, status=STATUS):
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        body = stats if request.url.path == "/control/stats" else status
        return httpx.Response(200, json=body)

    return httpx.MockTransport(handler), seen


def collect(store, transport, now=NOW):
    return asyncio.run(adguard.collect(CFG, store, transport=transport, now=now))


def test_reads_totals_hours_and_the_most_blocked_domain(store):
    transport, seen = answer()

    result = collect(store, transport)

    assert (result.queries, result.blocked, result.share) == (800, 96, 12.0)
    assert len(result.hours) == 24 and result.hours[-1].queries == 570
    assert result.hours[-1].blocked == 73
    assert (result.top_blocked, result.top_blocked_count) == ("doubleclick.net", 31)
    assert result.answering and result.protection and not result.stale
    assert [r.url.path for r in seen] == ["/control/stats", "/control/status"]
    assert seen[0].headers["Authorization"].startswith("Basic ")


def test_never_passes_on_which_device_asked(store):
    transport, _ = answer()

    payload = collect(store, transport).model_dump(mode="json")

    assert "192.168.1.20" not in str(payload)


def test_says_when_blocking_is_paused(store):
    transport, _ = answer(status=STATUS | {"protection_enabled": False})

    assert collect(store, transport).protection is False


def test_no_share_and_no_domain_before_any_query(store):
    empty = STATS | {"num_dns_queries": 0, "num_blocked_filtering": 0, "top_blocked_domains": []}
    transport, _ = answer(stats=empty)

    result = collect(store, transport)

    assert result.share is None and result.top_blocked is None


def down(_: httpx.Request) -> httpx.Response:
    raise httpx.ConnectError("refused")


def test_keeps_the_last_counts_and_says_not_answering_after_the_grace(store):
    transport, _ = answer()
    store.put_cache(adguard.CACHE_KEY, collect(store, transport).model_dump(mode="json"))
    gone = httpx.MockTransport(down)

    first = collect(store, gone, NOW + timedelta(minutes=1))
    store.put_cache(adguard.CACHE_KEY, first.model_dump(mode="json"))
    later = collect(store, gone, NOW + timedelta(minutes=1) + adguard.GRACE)

    assert first.answering and first.stale and first.queries == 800
    assert later.answering is False and later.failing_since == NOW + timedelta(minutes=1)


def test_answering_again_clears_the_failure(store):
    transport, _ = answer()
    failed = collect(store, transport).model_copy(
        update={"answering": False, "failing_since": NOW, "stale": True})
    store.put_cache(adguard.CACHE_KEY, failed.model_dump(mode="json"))

    result = collect(store, transport, NOW + timedelta(minutes=10))

    assert result.answering and result.failing_since is None and not result.stale


def test_a_refused_password_is_an_error_not_an_outage(store):
    transport, _ = answer()
    store.put_cache(adguard.CACHE_KEY, collect(store, transport).model_dump(mode="json"))

    with pytest.raises(httpx.HTTPStatusError):
        collect(store, httpx.MockTransport(lambda _: httpx.Response(401)))


def test_without_a_password_it_is_off():
    off = {"adguard": {"url": "http://nas:8053", "password": ""}}
    assert adguard.settings(off)["enabled"] is False
    assert adguard.settings(CFG)["url"] == "http://nas:8053"
