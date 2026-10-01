from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from fastapi.testclient import TestClient

from app import main
from app.models import ContainerState
from app.sources import container_stats

CFG = {"nas": {"docker_socket": "/nonexistent/docker.sock"}}


def stats(cpu_total, system_total, usage=600_000_000, cache=100_000_000, rx=1000, tx=500,
          cgroup="v2", networks=True):
    detail = {"inactive_file": cache} if cgroup == "v2" else {"total_inactive_file": cache}
    body = {
        "cpu_stats": {"cpu_usage": {"total_usage": cpu_total}, "system_cpu_usage": system_total,
                      "online_cpus": 6},
        "precpu_stats": {},
        "memory_stats": {"usage": usage, "limit": 8_000_000_000, "stats": detail},
    }
    if networks:
        body["networks"] = {"eth0": {"rx_bytes": rx, "tx_bytes": tx},
                            "eth1": {"rx_bytes": rx, "tx_bytes": tx}}
    return body


def test_parse_stats_leaves_out_page_cache_and_sums_networks():
    v2 = container_stats.parse_stats(stats(10, 100))
    v1 = container_stats.parse_stats(stats(10, 100, cgroup="v1"))
    host = container_stats.parse_stats(stats(10, 100, networks=False))

    assert (v2["mem_bytes"], v2["rx"], v2["tx"], v2["mem_limit"]) == (
        500_000_000, 2000, 1000, 8_000_000_000)
    assert v1["mem_bytes"] == 500_000_000
    assert (host["rx"], host["tx"]) == (None, None)  # host network: no own counters


def test_rates_need_a_previous_reading():
    now = container_stats.parse_stats(stats(1_500, 10_000, rx=7_000, tx=1_000))
    before = container_stats.parse_stats(stats(1_000, 5_000, rx=1_000, tx=400))

    assert container_stats.rates(now, None, 60) == (None, None, None)
    # 500 of 5,000 system ticks: 10% of the machine. Networks summed over two NICs.
    assert container_stats.rates(now, before, 60) == (10.0, 200.0, 20.0)


def test_rates_skip_counter_resets():
    now = container_stats.parse_stats(stats(100, 10_000, rx=10))
    before = container_stats.parse_stats(stats(5_000, 5_000, rx=9_000))

    cpu, rx, _ = container_stats.rates(now, before, 60)
    assert (cpu, rx) == (None, None)


CONTAINERS = [
    {"Id": "aaa111", "Names": ["/sonarr"], "Image": "lscr.io/linuxserver/sonarr:latest",
     "ImageID": "sha256:new", "State": "running", "Status": "Up 2 hours",
     "Labels": {"com.docker.compose.project": "sonarr"}},
    {"Id": "bbb222", "Names": ["/old"], "Image": "busybox", "ImageID": "sha256:b",
     "State": "exited", "Status": "Exited (0) 2 days ago", "Labels": {}},
]


def docker_api(cpu_total, system_total, seen=None):
    def handler(request: httpx.Request) -> httpx.Response:
        if seen is not None:
            seen.append(request)
        if request.url.path == "/containers/json":
            return httpx.Response(200, json=CONTAINERS)
        assert request.url.path == "/containers/aaa111/stats"
        return httpx.Response(200, json=stats(cpu_total, system_total))
    return httpx.MockTransport(handler)


def test_collect_reads_running_containers_one_shot_and_logs_samples(store):
    seen = []
    transport = docker_api(1_000, 5_000, seen)
    first = asyncio.run(container_stats.collect(CFG, store, transport=transport))

    by_name = {c.name: c for c in first.containers}
    sonarr, old = by_name["sonarr"], by_name["old"]
    assert (sonarr.name, sonarr.project, sonarr.cpu_pct, sonarr.mem_bytes) == (
        "sonarr", "sonarr", None, 500_000_000)
    assert (old.state, old.cpu_pct, old.mem_bytes) == ("exited", None, None)
    stats_calls = [r for r in seen if "stats" in r.url.path]
    assert len(stats_calls) == 1  # stopped containers are not asked
    assert dict(stats_calls[0].url.params) == {"stream": "false", "one-shot": "true"}

    # Pretend the first reading was a minute ago, then read again.
    counters = store.get_cache(container_stats.COUNTERS_KEY)
    counters["ts"] = (datetime.now(UTC) - timedelta(seconds=60)).isoformat()
    store.put_cache(container_stats.COUNTERS_KEY, counters)
    second = asyncio.run(container_stats.collect(CFG, store, transport=docker_api(1_500, 10_000)))

    assert {c.name: c.cpu_pct for c in second.containers}["sonarr"] == 10.0
    assert second.cpu_pct == 10.0
    assert second.mem_bytes == 500_000_000
    assert len(store.container_samples("sonarr", datetime.now(UTC) - timedelta(hours=1))) == 2


def test_collect_raises_without_a_socket(store):
    with pytest.raises(RuntimeError):
        asyncio.run(container_stats.collect(CFG, store))


def _c(name, image_id, image="img:latest"):
    return ContainerState(name=name, state="running", image=image, image_id=image_id)


def test_image_changes_are_logged_as_updates(store):
    now = datetime(2026, 10, 1, 4, 0, tzinfo=UTC)

    assert container_stats.note_updates(store, [_c("sonarr", "sha:1")], now) == []
    assert container_stats.note_updates(store, [_c("sonarr", "sha:1")], now) == []
    # Watchtower stops the container, then recreates it from the new image.
    assert container_stats.note_updates(store, [], now) == []
    assert container_stats.note_updates(store, [_c("sonarr", "sha:2")], now) == ["sonarr"]

    (row,) = store.container_updates()
    assert (row["name"], row["image"], row["old_image_id"], row["new_image_id"]) == (
        "sonarr", "img:latest", "sha:1", "sha:2")


def test_history_averages_into_ten_minute_buckets(store):
    base = datetime(2026, 10, 1, 12, 0, tzinfo=UTC)
    for minute, cpu, mem in [(0, 2.0, 100), (5, 4.0, 300), (9, None, None), (12, 8.0, 500)]:
        store.put_container_sample(base + timedelta(minutes=minute), "sonarr", cpu, mem)

    points = container_stats.history(store.container_samples("sonarr", base))

    assert [(p.t.minute, p.cpu, p.mem) for p in points] == [(0, 3.0, 200), (10, 8.0, 500)]


def test_docker_endpoints(store):
    main.app.state.store = store
    main.app.state.config = {}
    client = TestClient(main.app)
    assert client.get("/api/docker").status_code == 503

    store.put_container_sample(datetime.now(UTC), "sonarr", 1.5, 1000)
    store.add_container_update(datetime(2026, 10, 1, 4, 0, tzinfo=UTC), "sonarr", "img", "a", "b")

    assert client.get("/api/docker/history/sonarr").json()[0]["cpu"] == 1.5
    assert client.get("/api/docker/history/nothing").json() == []
    assert client.get("/api/docker/updates").json() == [{
        "at": "2026-10-01T04:00:00Z", "name": "sonarr", "image": "img",
        "old_image_id": "a", "new_image_id": "b"}]
