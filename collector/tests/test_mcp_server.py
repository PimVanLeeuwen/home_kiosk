from __future__ import annotations

import asyncio
import contextlib
import json

from fastapi.testclient import TestClient
from mcp.client import Client
from starlette.applications import Starlette
from starlette.routing import Route

from app import main, mcp_house, mcp_server, reminders
from app.sources import agenda

TRAIN = {
    "as_of": "2026-11-12T06:40:00Z",
    "stale": False,
    "date": "2026-11-12",
    "route": "Leiden Centraal to Rotterdam Centraal",
    "departure": "07:16",
    "mode": "morning",
    "watching": True,
    "departed": False,
    "train": {
        "name": "IC 3522",
        "status": "late",
        "planned_departure": "2026-11-12T06:16:00Z",
        "actual_departure": "2026-11-12T06:20:00Z",
        "delay_minutes": 4,
        "planned_track": "5",
        "actual_track": "8b",
        "stops": [
            {"name": "Leiden Centraal", "planned": "2026-11-12T06:16:00Z", "actual": None,
             "track": "8b"},
            {"name": "Rotterdam Centraal", "planned": "2026-11-12T06:50:00Z", "actual": None,
             "track": "12"},
        ],
    },
    "next_direct": None,
}

BACKUPS = {
    "as_of": "2026-11-12T03:40:00Z",
    "stale": False,
    "runs": [{"started": "x", "finished": "y", "ok": True, "volumes": []}],
    "volumes": [
        {
            "name": "volume1",
            "last_run": {
                "started": "2026-11-12T02:00:00Z",
                "finished": "2026-11-12T02:30:00Z",
                "ok": False,
                "volumes": [
                    {"name": "volume1", "ok": True, "exit_code": 0, "seconds": 600, "errors": 0},
                    {"name": "volume3", "ok": False, "exit_code": 1, "seconds": 900,
                     "errors": 2, "last_error": "quota exceeded"},
                ],
            },
            "last_success": "2026-11-12T02:30:00Z",
        },
        {"name": "volume3", "last_run": None, "last_success": None},
    ],
    "next_due": "2026-11-13T02:00:00Z",
    "storage_box": {"total": 10, "used": 6, "free": 4, "used_pct": 60.0,
                    "at": "2026-11-12T02:30:00Z", "projection_months": 14.5},
}


def test_train_keeps_the_card_and_names_the_stops_only():
    out = mcp_house.train(TRAIN)

    assert out["train"]["track"] == "8b"
    assert out["train"]["delay_minutes"] == 4
    assert out["train"]["stops"] == ["Leiden Centraal", "Rotterdam Centraal"]
    assert out["next_direct"] is None
    assert out["route"] == "Leiden Centraal to Rotterdam Centraal"


def test_backups_give_each_volume_its_own_result_and_drop_the_run_list():
    out = mcp_house.backups(BACKUPS)

    assert "runs" not in out
    first, second = out["volumes"]
    assert first == {
        "name": "volume1", "last_run_finished": "2026-11-12T02:30:00Z", "last_run_ok": True,
        "last_run_errors": 0, "last_error": None, "last_success": "2026-11-12T02:30:00Z",
    }
    assert second["last_run_ok"] is None and second["last_success"] is None
    assert out["storage_box"] == {"used_pct": 60.0, "free_bytes": 4, "months_until_full": 14.5}


def test_nas_drops_the_network_history():
    payload = {"as_of": "t", "cpu_pct": 12.0,
               "network": {"rx_mbps": 1.0, "tx_mbps": 2.0, "history": [{"t": "t", "rx": 1}]}}

    out = mcp_house.nas(payload)

    assert out["network"] == {"rx_mbps": 1.0, "tx_mbps": 2.0}
    assert out["cpu_pct"] == 12.0
    assert "history" in payload["network"]  # the cached payload is not touched


def test_nothing_cached_yet_says_so():
    for summary in (mcp_house.train, mcp_house.backups, mcp_house.nas, mcp_house.calendar,
                    mcp_house.weather, mcp_house.forecast, mcp_house.air, mcp_house.laundry,
                    mcp_house.docker,
                    mcp_house.media, mcp_house.sites, mcp_house.outside):
        assert summary(None)["available"] is False


def test_calendar_keeps_titles_and_times_only_for_today_and_tomorrow():
    payload = {
        "as_of": "t", "date": "2026-11-12", "errors": {"work": "401"},
        "events": [{"calendar_id": "abc", "calendar": "Work", "color": "#f00",
                    "title": "Dentist", "start": "10:00", "end": "10:30", "all_day": False}],
        "all_day": [],
        "tomorrow": {"date": "2026-11-13", "all_day": [],
                     "events": [{"title": "Later", "calendar": "Work", "start": "9:00",
                                 "end": None, "all_day": False}]},
    }

    one = mcp_house.calendar(payload, 1)
    two = mcp_house.calendar(payload, 2)

    assert one["days"] == [{"date": "2026-11-12", "all_day": [], "events": [
        {"title": "Dentist", "start": "10:00", "end": "10:30", "all_day": False}]}]
    assert [d["date"] for d in two["days"]] == ["2026-11-12", "2026-11-13"]
    assert "calendar" not in two["days"][1]["events"][0]
    assert one["unread_calendars"] == 1


def test_a_calendar_range_read_on_the_spot_is_trimmed_the_same_way():
    event = agenda.CalendarEvent(calendar_id="abc", calendar="Work", color="#f00",
                                 title="Trip", start=None, end=None, all_day=True)
    out = mcp_house.calendar_days({"as_of": "t", "errors": {},
                                   "days": [{"date": "2026-12-01", "events": [],
                                             "all_day": [event]}]})

    assert out["days"] == [{"date": "2026-12-01", "events": [], "all_day": [
        {"title": "Trip", "start": None, "end": None, "all_day": True}]}]


def test_forecast_gives_every_day_or_one_with_its_hours():
    payload = {"as_of": "t", "days": [
        {"date": "2026-11-12", "high": 11.0, "low": 4.0, "code": 61, "rain_max": 80,
         "rain_mm": 3.5, "sunrise": "08:00", "sunset": "16:50",
         "hours": [{"hour": 9, "temperature": 7.0, "rain_chance": 60, "rain_mm": 0.4}]},
        {"date": "2026-11-13", "high": 9.0, "low": 2.0, "hours": []},
    ]}

    week = mcp_house.forecast(payload)
    one = mcp_house.forecast(payload, "2026-11-13")

    assert [d["date"] for d in week["days"]] == ["2026-11-12", "2026-11-13"]
    assert week["days"][0]["rain_mm"] == 3.5
    assert week["days"][0]["hours"] == [{"hour": 9, "temperature": 7.0, "rain_chance": 60,
                                         "rain_mm": 0.4}]
    assert [d["date"] for d in one["days"]] == ["2026-11-13"]
    assert one["known_days"] == ["2026-11-12", "2026-11-13"]


def test_air_and_weather_drop_history_and_the_station():
    air = mcp_house.air({"as_of": "t", "co2": 640, "history": [{"at": "t", "co2": 600}]})
    weather = mcp_house.weather({"as_of": "t", "station": "Somewhere", "temperature": 9.5,
                                 "rain": [{"at": "t", "mm_per_hour": 0.0}]})

    assert air == {"as_of": "t", "co2": 640}
    assert "station" not in weather and weather["temperature"] == 9.5
    assert weather["rain"] == [{"at": "t", "mm_per_hour": 0.0}]


def test_docker_media_and_services_drop_paths_and_ids():
    docker = mcp_house.docker({"as_of": "t", "cpu_pct": 3.0, "mem_bytes": 2_500_000_000,
                               "containers": [{"name": "jellyfin", "project": "jellyfin",
                                               "image": "x", "state": "running",
                                               "mem_bytes": 300_000_000, "rx_bps": 1.0}]})
    media = mcp_house.media({"as_of": "t", "downloads": [
        {"id": "sonarr:1", "kind": "tv", "title": "Show", "poster": "sonarr/1",
         "progress_pct": 40.0, "state": "downloading"}],
        "missing": [], "upcoming": [], "errors": {"radarr": "down"}, "posters": {"a": "b"}})
    services = mcp_house.services({"as_of": "t", "groups": [{"name": "Media", "services": [
        {"id": "jf", "name": "Jellyfin", "port": 8096, "icon": "jf", "status": "up",
         "stats": [{"label": "Streams", "value": 1, "unit": ""}]}]}]})

    assert docker["mem_mb"] == 2500.0
    assert docker["containers"][0]["mem_mb"] == 300.0
    assert docker["containers"][0]["image"] == "x"
    assert "poster" not in media["downloads"][0] and "id" not in media["downloads"][0]
    assert "posters" not in media and media["unread_sources"] == ["radarr"]
    assert services["groups"][0]["services"] == [
        {"name": "Jellyfin", "description": None, "status": "up", "container": None,
         "port": 8096, "path": None, "url": None,
         "stats": [{"label": "Streams", "value": 1, "unit": ""}]}]


def test_outside_gives_each_incident_its_latest_word():
    out = mcp_house.outside({"as_of": "t", "services": [{
        "key": "gh", "name": "GitHub", "url": "u", "state": "degraded", "stale": False,
        "incidents": [{"title": "Actions slow", "impact": "degraded", "status": "monitoring",
                       "url": "u", "updates": [{"text": "first"}, {"text": "fixed, watching"}]}],
    }]})

    assert out["services"][0]["incidents"][0]["latest"] == "fixed, watching"
    assert "url" not in out["services"][0]


def test_alerts_keep_open_incidents_and_drop_chat_ids_and_html():
    messages = [{"id": 1, "ts": "t", "source": "rclone", "category": "backup",
                 "severity": "info", "title": "Backup done", "body": "ok", "chat": "nas",
                 "status": "sent", "channel": "ntfy", "ntfy_id": "x", "html": "<b>"}]
    incidents = [
        {"rule": "disk", "severity": "warn", "title": "Disk full", "body": "90%",
         "opened_at": "t", "last_seen_at": "t", "resolved_at": None, "dismissed_at": None},
        {"rule": "old", "title": "Gone", "resolved_at": "t", "dismissed_at": None},
    ]

    out = mcp_house.alerts(messages, incidents)

    assert out["messages"] == [{"id": 1, "ts": "t", "category": "backup", "severity": "info",
                                "title": "Backup done", "body": "ok", "status": "sent",
                                "channel": "ntfy"}]
    assert [i["title"] for i in out["open_incidents"]] == ["Disk full"]


ALL_TOOLS = ["air", "alerts", "backups", "calendar", "docker", "forecast", "laundry", "lights",
             "media", "music", "nas",
             "outside_services", "reminders", "services", "train", "weather", "websites"]


def test_every_tool_answers_on_an_empty_hub(store):
    reminders.ensure_tables(store)
    server = mcp_server.build(lambda: store, lambda: {"timezone": "Europe/Amsterdam"})

    async def ask():
        async with Client(server) as client:
            return {name: await client.call_tool(name, {}) for name in ALL_TOOLS}

    results = asyncio.run(ask())

    for name, result in results.items():
        if name == "music":  # asks Spotify itself, which is not set up here
            assert result.is_error and "not set up" in result.content[0].text
        else:
            assert not result.is_error, name


def test_tools_are_read_only_and_answer_from_the_cache(store):
    store.put_cache("train", TRAIN)
    server = mcp_server.build(lambda: store, lambda: {})

    async def ask():
        async with Client(server) as client:
            tools = (await client.list_tools()).tools
            result = await client.call_tool("train", {})
            missing = await client.call_tool("backups", {})
            return tools, result, missing

    tools, result, missing = asyncio.run(ask())

    assert sorted(t.name for t in tools) == ALL_TOOLS
    assert all(t.annotations.read_only_hint for t in tools)
    assert result.structured_content["train"]["name"] == "IC 3522"
    assert missing.structured_content["available"] is False


HEADERS = {"Accept": "application/json, text/event-stream", "Content-Type": "application/json"}
TOKEN = "s3cret-write-token"


def http_app(store, token: str = TOKEN) -> Starlette:
    """The /mcp endpoint as the app routes it: the read server, and the write one by token."""
    read = mcp_server.build(lambda: store, lambda: {})
    write = mcp_server.build(lambda: store, lambda: {}, writes=True)

    @contextlib.asynccontextmanager
    async def lifespan(_):
        async with read.session_manager.run(), write.session_manager.run():
            yield

    return Starlette(routes=[Route(mcp_server.PATH,
                                   mcp_server.http_endpoint(read, write, lambda: token),
                                   methods=["GET", "POST", "DELETE"])], lifespan=lifespan)


def rpc(client, method: str, params: dict, headers: dict | None = None):
    """An initialize, then `method`, as a client over HTTP does it."""
    headers = {**HEADERS, **(headers or {})}
    resp = client.post(mcp_server.PATH, headers=headers, json={
        "jsonrpc": "2.0", "id": 1, "method": "initialize",
        "params": {"protocolVersion": "2025-06-18", "capabilities": {},
                   "clientInfo": {"name": "test", "version": "1"}}})
    if resp.status_code != 200:
        return resp
    version = resp.json()["result"]["protocolVersion"]
    return client.post(mcp_server.PATH, headers={**headers, "MCP-Protocol-Version": version},
                       json={"jsonrpc": "2.0", "id": 2, "method": method, "params": params})


def test_answers_over_http(store):
    store.put_cache("nas", {"as_of": "t", "cpu_pct": 7.5})

    with TestClient(http_app(store)) as client:
        resp = rpc(client, "tools/call", {"name": "nas", "arguments": {}})

    assert resp.status_code == 200, resp.text
    content = resp.json()["result"]["content"][0]["text"]
    assert json.loads(content)["cpu_pct"] == 7.5


def tool_names(resp) -> set[str]:
    assert resp.status_code == 200, resp.text
    return {t["name"] for t in resp.json()["result"]["tools"]}


def test_the_write_tools_only_show_with_the_write_token(store):
    with TestClient(http_app(store)) as client:
        plain = tool_names(rpc(client, "tools/list", {}))
        with_token = tool_names(rpc(client, "tools/list", {},
                                    {"Authorization": f"Bearer {TOKEN}"}))

    writes = {"lights_room", "lights_change", "music_control", "music_volume",
              "music_play_favourite", "add_reminder", "tick_reminder", "send_test_message"}
    assert plain == set(ALL_TOOLS)
    assert with_token == set(ALL_TOOLS) | writes


def test_a_wrong_token_or_none_set_up_is_a_401(store):
    with TestClient(http_app(store)) as client:
        wrong = rpc(client, "tools/list", {}, {"Authorization": "Bearer guess"})
        basic = rpc(client, "tools/list", {}, {"Authorization": f"Basic {TOKEN}"})
    with TestClient(http_app(store, token="")) as client:
        unset = rpc(client, "tools/list", {}, {"Authorization": f"Bearer {TOKEN}"})

    assert wrong.status_code == basic.status_code == unset.status_code == 401
    assert "not set up" in unset.json()["detail"]


def test_the_write_token_comes_from_the_config():
    assert mcp_server.write_token({"mcp": {"write_token": " abc "}}) == "abc"
    assert mcp_server.write_token({}) == ""


def test_the_app_refuses_browsers_at_mcp(store):
    main.app.state.store = store
    client = TestClient(main.app)

    resp = client.post(mcp_server.PATH, headers={"Origin": "https://evil.example"},
                       json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"})

    assert resp.status_code == 403


def test_reminders_cover_a_range_of_days_with_their_ticks(store):
    from datetime import date

    reminders.ensure_tables(store)
    bins = reminders.add(store, reminders.Draft.model_validate({
        "title": "Bins out", "start": "2026-11-10",
        "repeat": {"kind": "weekly", "weekdays": [3]}}))  # Thursdays
    reminders.set_done(store, bins.id, date(2026, 11, 12), True)
    server = mcp_server.build(lambda: store, lambda: {"timezone": "Europe/Amsterdam"})

    async def ask():
        async with Client(server) as client:
            return await client.call_tool("reminders", {"start": "2026-11-12", "days": 8})

    out = asyncio.run(ask()).structured_content

    falls = {d["date"]: d["reminders"] for d in out["days"] if d["reminders"]}
    assert falls == {"2026-11-12": [{"id": bins.id, "title": "Bins out", "at": None,
                                     "done": True}],
                     "2026-11-19": [{"id": bins.id, "title": "Bins out", "at": None,
                                     "done": False}]}
    assert len(out["days"]) == 8


def test_a_wrong_date_is_a_tool_error_that_says_how(store):
    server = mcp_server.build(lambda: store, lambda: {})

    async def ask():
        async with Client(server) as client:
            return await client.call_tool("calendar", {"start": "12-11-2026", "days": 5})

    result = asyncio.run(ask())

    assert result.is_error
    assert "YYYY-MM-DD" in result.content[0].text
