from __future__ import annotations

import asyncio
import json

from fastapi.testclient import TestClient
from mcp.client import Client
from starlette.applications import Starlette
from starlette.routing import Route

from app import main, mcp_server

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
    out = mcp_server.train_summary(TRAIN)

    assert out["train"]["track"] == "8b"
    assert out["train"]["delay_minutes"] == 4
    assert out["train"]["stops"] == ["Leiden Centraal", "Rotterdam Centraal"]
    assert out["next_direct"] is None
    assert out["route"] == "Leiden Centraal to Rotterdam Centraal"


def test_backups_give_each_volume_its_own_result_and_drop_the_run_list():
    out = mcp_server.backups_summary(BACKUPS)

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

    out = mcp_server.nas_summary(payload)

    assert out["network"] == {"rx_mbps": 1.0, "tx_mbps": 2.0}
    assert out["cpu_pct"] == 12.0
    assert "history" in payload["network"]  # the cached payload is not touched


def test_nothing_cached_yet_says_so():
    for summary in (mcp_server.train_summary, mcp_server.backups_summary,
                    mcp_server.nas_summary):
        assert summary(None)["available"] is False


def test_tools_are_read_only_and_answer_from_the_cache(store):
    store.put_cache("train", TRAIN)
    server = mcp_server.build(lambda: store)

    async def ask():
        async with Client(server) as client:
            tools = (await client.list_tools()).tools
            result = await client.call_tool("train", {})
            missing = await client.call_tool("backups", {})
            return tools, result, missing

    tools, result, missing = asyncio.run(ask())

    assert sorted(t.name for t in tools) == ["backups", "nas", "train"]
    assert all(t.annotations.read_only_hint for t in tools)
    assert result.structured_content["train"]["name"] == "IC 3522"
    assert missing.structured_content["available"] is False


def test_answers_over_http(store):
    store.put_cache("nas", {"as_of": "t", "cpu_pct": 7.5})
    server = mcp_server.build(lambda: store)
    app = Starlette(routes=[Route(mcp_server.PATH, mcp_server.http_endpoint(server),
                                  methods=["GET", "POST", "DELETE"])],
                    lifespan=lambda _: server.session_manager.run())
    headers = {"Accept": "application/json, text/event-stream",
               "Content-Type": "application/json"}

    with TestClient(app) as client:
        resp = client.post(mcp_server.PATH, headers=headers, json={
            "jsonrpc": "2.0", "id": 1, "method": "initialize",
            "params": {"protocolVersion": "2025-06-18", "capabilities": {},
                       "clientInfo": {"name": "test", "version": "1"}}})
        assert resp.status_code == 200, resp.text
        version = resp.json()["result"]["protocolVersion"]
        resp = client.post(mcp_server.PATH, headers={**headers, "MCP-Protocol-Version": version},
                           json={"jsonrpc": "2.0", "id": 2, "method": "tools/call",
                                 "params": {"name": "nas", "arguments": {}}})

    assert resp.status_code == 200, resp.text
    content = resp.json()["result"]["content"][0]["text"]
    assert json.loads(content)["cpu_pct"] == 7.5


def test_the_app_refuses_browsers_at_mcp(store):
    main.app.state.store = store
    client = TestClient(main.app)

    resp = client.post(mcp_server.PATH, headers={"Origin": "https://evil.example"},
                       json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"})

    assert resp.status_code == 403
