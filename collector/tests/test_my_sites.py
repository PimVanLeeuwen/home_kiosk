from __future__ import annotations

import asyncio
import json
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx
import pytest
from fastapi.testclient import TestClient

from app import main
from app.models import Service
from app.sources import my_sites

FIXTURES = Path(__file__).parent / "fixtures"
PAGE = json.loads((FIXTURES / "kuma_sites.json").read_text())
BEATS = json.loads((FIXTURES / "kuma_sites_heartbeat.json").read_text())
AMS = ZoneInfo("Europe/Amsterdam")
CFG = {"timezone": "Europe/Amsterdam", "widgets": {"host": "nas"},
       "my_sites": {"kuma_slug": "sites"}}
NOW = datetime(2026, 10, 14, 9, 16, tzinfo=UTC)


@pytest.fixture
def sites_store(store):
    my_sites.ensure_tables(store)
    store.seed_services([Service(id="uptime-kuma", name="Uptime Kuma", group="Monitoring",
                                 port=3001, container="uptime-kuma", widget="uptimekuma")])
    return store


def beats(start: str, statuses: str, every: int = 60) -> list[dict]:
    """One heartbeat a minute from `start` (UTC), "1" up and "0" down."""
    t0 = datetime.fromisoformat(start)
    return [{"status": int(s), "ping": 120, "msg": "",
             "time": (t0 + timedelta(seconds=i * every)).strftime("%Y-%m-%d %H:%M:%S")}
            for i, s in enumerate(statuses)]


def kuma(heartbeats: dict = BEATS, fail: bool = False) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.host == "nas" and request.url.port == 3001
        if fail:
            return httpx.Response(502)
        if request.url.path == "/api/status-page/sites":
            return httpx.Response(200, json=PAGE)
        if request.url.path == "/api/status-page/heartbeat/sites":
            return httpx.Response(200, json=heartbeats)
        return httpx.Response(404)

    return httpx.MockTransport(handler)


def collect(store, heartbeats: dict = BEATS, now: datetime = NOW) -> my_sites.Sites:
    return asyncio.run(my_sites.collect(CFG, store, now=now, transport=kuma(heartbeats)))


def test_reads_kumas_groups_and_names_trimmed(sites_store):
    result = collect(sites_store)

    assert [(s.group, s.name) for s in result.sites] == [
        ("Personal", "AOC"), ("Personal", "Portfolio"),
        ("Hubble", "Harry List Admin"), ("Hubble", "Hubble Website"),
        ("Hubble", "Harry List Public"), ("Hubble", "Admin Website"),
        ("Hubble", "Meteor Website")]
    assert all(s.up for s in result.sites)
    # 99 minutes of up time today from the real heartbeats: a full green day so far.
    assert result.sites[0].days[-1] == "up" and result.sites[0].days[:-1] == ["none"] * 29
    assert result.sites[0].uptime_pct == 100.0


def test_heartbeats_are_counted_once_however_often_they_are_read(sites_store):
    collect(sites_store)
    collect(sites_store)

    days, _ = my_sites.history(sites_store, 13, date(2026, 10, 14))
    with sites_store.connect() as conn:
        up = conn.execute("SELECT up_seconds FROM site_day WHERE monitor_id = 13").fetchone()[0]
    assert days[-1] == "up" and up == 99 * 60


def test_more_than_five_minutes_down_is_an_outage_less_a_blip(sites_store):
    my_sites.record(sites_store, 1, beats("2026-10-13 08:00:00", "1110000000111"), AMS)
    my_sites.record(sites_store, 2, beats("2026-10-13 08:00:00", "1110011111"), AMS)

    outage, uptime = my_sites.history(sites_store, 1, date(2026, 10, 13))
    blip, _ = my_sites.history(sites_store, 2, date(2026, 10, 13))

    # Each gap counts towards the beat it ends at: 5 minutes up, 7 down.
    assert outage[-1] == "down" and uptime == pytest.approx(41.67)
    assert blip[-1] == "blip"


def test_a_long_gap_counts_as_nothing(sites_store):
    my_sites.record(sites_store, 1, beats("2026-10-13 08:00:00", "11"), AMS)
    # The hub was off for an hour; the next beat is down, but the hour is not.
    my_sites.record(sites_store, 1, beats("2026-10-13 09:01:00", "01"), AMS)

    with sites_store.connect() as conn:
        row = conn.execute("SELECT up_seconds, down_seconds FROM site_day").fetchone()
    assert (row["up_seconds"], row["down_seconds"]) == (120, 0)


def test_days_follow_amsterdam_not_utc(sites_store):
    # 22:30 to 22:32 UTC on the 13th is already the 14th in Amsterdam.
    my_sites.record(sites_store, 1, beats("2026-10-13 22:30:00", "111"), AMS)

    days, _ = my_sites.history(sites_store, 1, date(2026, 10, 14))
    assert days[-1] == "up" and days[-2] == "none"


def test_a_site_down_now_says_since_when(sites_store):
    down = json.loads(json.dumps(BEATS))
    tail = down["heartbeatList"]["43"]
    for beat in tail[-2:]:
        beat["status"] = 0

    meteor = next(s for s in collect(sites_store, down).sites if s.id == 43)

    assert meteor.up is False
    assert meteor.down_since == datetime.fromisoformat(tail[-2]["time"]).replace(tzinfo=UTC)


def test_no_heartbeats_yet_is_unknown(sites_store):
    empty = {"heartbeatList": {}, "uptimeList": {}}

    site = collect(sites_store, empty).sites[0]

    assert site.up is None and site.uptime_pct is None and site.days == ["none"] * 30


def test_kuma_down_raises_so_the_last_answer_goes_stale(sites_store):
    with pytest.raises(httpx.HTTPStatusError):
        asyncio.run(my_sites.collect(CFG, sites_store, now=NOW, transport=kuma(fail=True)))


def test_switched_off_without_a_slug_or_kuma(sites_store, store):
    assert my_sites.settings(CFG, sites_store)["enabled"] is True
    assert my_sites.settings({"my_sites": {"kuma_slug": ""}}, sites_store)["enabled"] is False


def test_the_route_serves_the_answer(sites_store):
    # No `with`: the lifespan would start the scheduler and hit real sources.
    main.app.state.store = sites_store
    main.app.state.config = CFG
    client = TestClient(main.app)
    assert client.get("/api/sites").status_code == 503

    sites_store.put_cache(my_sites.CACHE_KEY, collect(sites_store).model_dump(mode="json"))

    assert len(client.get("/api/sites").json()["sites"]) == 7
