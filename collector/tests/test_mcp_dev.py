from __future__ import annotations

import asyncio
import json
import logging
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from mcp.client import Client
from mcp.server.mcpserver.exceptions import ToolError

from app import desk_boards, logbuffer, mcp_dev, mcp_server, scheduler


def call(store, name: str, args: dict | None = None, sched=None):
    server = mcp_server.build(lambda: store, lambda: {"timezone": "Europe/Amsterdam"},
                              sched=lambda: sched)

    async def ask():
        async with Client(server) as client:
            return await client.call_tool(name, args or {})

    return asyncio.run(ask())


def test_shape_and_sample():
    payload = {"title": "x" * 400, "n": 3, "items": [{"a": 1}, {"a": 2}, {"a": 3}, {"a": 4}],
               "empty": []}

    assert mcp_dev.shape(payload) == {"title": "str", "n": "int",
                                      "items": {"list_of": {"a": "int"}, "length": 4},
                                      "empty": {"list_of": None, "length": 0}}
    cut = mcp_dev.sample(payload)
    assert cut["items"] == [{"a": 1}, {"a": 2}, {"a": 3}, "... 1 more"]
    assert cut["title"].endswith("...") and len(cut["title"]) == 303


def test_source_sample_shows_personal_sources_by_shape_only(store):
    store.put_cache("calendar", {"events": [{"title": "Dentist"}]})
    store.put_cache("nas", {"cpu_pct": 12.5})

    keys = call(store, "source_sample").structured_content["keys"]
    calendar = call(store, "source_sample", {"key": "calendar"}).structured_content
    nas = call(store, "source_sample", {"key": "nas"}).structured_content
    missing = call(store, "source_sample", {"key": "nope"})

    assert {k["key"]: k["values"] for k in keys} == {"calendar": False, "nas": True}
    assert "Dentist" not in json.dumps(calendar)
    assert calendar["shape"] == {"events": {"list_of": {"title": "str"}, "length": 1}}
    assert nas["payload"] == {"cpu_pct": 12.5}
    assert missing.is_error and "Nothing cached" in missing.content[0].text


def test_job_status_joins_the_schedule_with_the_last_refresh(store, monkeypatch):
    sched = AsyncIOScheduler(timezone="UTC")

    async def job():
        return None

    sched.add_job(scheduler._run, "interval", minutes=5, args=[store, "nas", job], id="nas",
                  next_run_time=datetime(2026, 11, 12, 12, tzinfo=UTC))
    sched.add_job(job, "cron", hour=6, id="briefing")
    monkeypatch.setattr(scheduler, "REFRESHES", {"nas": {
        "at": datetime(2026, 11, 12, 11, 55, tzinfo=UTC), "ok": False, "error": "ReadTimeout"}})
    monkeypatch.setattr(scheduler, "RUNS", {"nas": {
        "at": datetime(2026, 11, 12, 11, 55, tzinfo=UTC), "missed": False, "error": None}})

    jobs = {j["id"]: j for j in mcp_dev.jobs(sched)}

    assert jobs["nas"]["ok"] is False and jobs["nas"]["error"] == "ReadTimeout"
    assert jobs["nas"]["cache_key"] == "nas"
    assert jobs["nas"]["next_run"] == "2026-11-12T12:00:00+00:00"
    assert jobs["briefing"]["ok"] is None and jobs["briefing"]["last_run"] is None
    assert mcp_dev.jobs(None) == []


def test_a_failed_refresh_is_recorded_by_its_class_only(store, monkeypatch):
    monkeypatch.setattr(scheduler, "REFRESHES", {})

    async def boom():
        raise RuntimeError("https://x.example/api?apikey=s3cret")

    asyncio.run(scheduler._run(store, "media", boom))

    assert scheduler.REFRESHES["media"]["ok"] is False
    assert scheduler.REFRESHES["media"]["error"] == "RuntimeError"


def test_hub_logs_keep_the_level_and_window_and_redact():
    handler = logbuffer.RingHandler(keep=10)
    logger = logging.getLogger("test.mcp.logs")
    logger.addHandler(handler)
    logger.propagate = False
    logger.setLevel(logging.INFO)
    try:
        logger.info("refreshed nas")
        logger.warning("sabnzbd failed: https://nas:8085/api?apikey=%s", "0123456789abcdef" * 2)
    finally:
        logger.removeHandler(handler)
    handler.records[0]["at"] -= timedelta(hours=2)

    recent = logbuffer.recent(60, "INFO", handler=handler)
    warnings = logbuffer.recent(600, "warning", handler=handler)

    assert [r["level"] for r in recent] == ["WARNING"]
    assert "0123456789abcdef" not in recent[0]["text"]
    assert [r["level"] for r in warnings] == ["WARNING"]


def docker_transport(seen: list[str]) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.url.path + "?" + request.url.query.decode())
        if request.url.path == "/containers/sonarr/logs":
            line = b"2026-11-12T10:00:00Z GET http://10.0.0.5/api?apikey=abc user me@example.com\n"
            return httpx.Response(200, content=b"\x01\x00\x00\x00" + len(line).to_bytes(4, "big")
                                  + line)
        if request.url.path == "/containers/json":
            return httpx.Response(200, json=[
                {"Names": ["/home-kiosk-collector"],
                 "Image": "pimvanleeuwen/home-kiosk-collector:latest",
                 "ImageID": "sha256:0123456789abcdef", "State": "running", "Status": "Up 2 hours",
                 "Labels": {mcp_dev.REVISION: "abc1234"}},
                {"Names": ["/jellyfin"], "Image": "jellyfin/jellyfin", "Labels": {}},
            ])
        return httpx.Response(404)

    return httpx.MockTransport(handler)


def test_container_logs_are_demuxed_redacted_and_capped():
    seen: list[str] = []

    out = asyncio.run(mcp_dev.container_logs("/x", "sonarr", 5000, docker_transport(seen)))

    assert "tail=200" in seen[0]
    assert "10.0.0.5" not in out["log"] and "me@example.com" not in out["log"]
    assert "apikey=abc" not in out["log"]
    assert out["log"].startswith("2026-11-12T10:00:00Z GET")


@pytest.mark.parametrize("name", ["../etc", "a/b", "", "x?y"])
def test_container_logs_refuse_a_name_that_is_not_one(name):
    with pytest.raises(ToolError):
        asyncio.run(mcp_dev.container_logs("/x", name, 10, docker_transport([])))


def test_container_logs_name_an_unknown_container():
    with pytest.raises(ToolError, match="No container called 'nope'"):
        asyncio.run(mcp_dev.container_logs("/x", "nope", 10, docker_transport([])))


def test_deployed_version_reads_the_revision_label_and_the_last_ci_run():
    pipelines = {"repos": [{"name": "home_kiosk", "run": {
        "sha": "abc1234", "commit": "feat(mcp): x", "state": "success",
        "started_at": "t", "ended_at": "t", "failed": None, "jobs": []}}]}

    out = asyncio.run(mcp_dev.deployed("/x", pipelines, docker_transport([])))

    assert out["containers"] == [{"name": "home-kiosk-collector",
                                  "image": "pimvanleeuwen/home-kiosk-collector:latest",
                                  "image_id": "0123456789ab", "state": "running",
                                  "status": "Up 2 hours", "revision": "abc1234"}]
    assert out["latest_ci_run"]["sha"] == "abc1234" and out["note"] is None


def test_panel_state_lists_screen_kinds_without_content(store):
    desk_boards.ensure_tables(store)
    desk_boards.check_in(store, "e8:f6:0a:e4:42:b0", "1.2.3")

    boards = call(store, "panel_state").structured_content["boards"]

    assert [b["mac"] for b in boards] == ["e8:f6:0a:e4:42:b0"]
    assert boards[0]["firmware"] == "1.2.3" and boards[0]["panel"] is None
    assert "screens" not in boards[0]  # not assigned to a panel yet
