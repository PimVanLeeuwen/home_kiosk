from __future__ import annotations

import asyncio
import json
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from app import main
from app.sources import air

NOW = datetime(2026, 10, 21, 12, 0, tzinfo=UTC)
CFG = {"air": {"matter": "ws://nas:5580/ws", "node": 1, "room": "Living room"}}

# As the ALPSTUGA (firmware 1.0.26) answers through the Matter server: endpoint 1.
NODE = {"node_id": 1, "available": True, "attributes": {
    "0/40/1": "IKEA of Sweden", "0/40/3": "ALPSTUGA air quality monitor",
    "1/91/0": 1, "1/1026/0": 2300, "1/1029/0": 4612, "1/1037/0": 391.0, "1/1037/8": 0,
    "1/1066/0": 3.0, "1/1066/8": 4}}


class FakeServer:
    """The Matter server's side of one WebSocket: its info first, then answers."""

    def __init__(self, node=NODE, noise=False, error=None):
        self.inbox = [json.dumps({"fabric_id": 1, "schema_version": 14})]
        self.node, self.noise, self.error, self.sent = node, noise, error, []

    async def send(self, message):
        request = json.loads(message)
        self.sent.append(request)
        if self.noise:  # an event that is not the answer
            self.inbox.append(json.dumps({"event": "node_updated", "data": {}}))
        if self.error:
            self.inbox.append(json.dumps({"message_id": request["message_id"],
                                          "error_code": 5, "details": self.error}))
        else:
            self.inbox.append(json.dumps({"message_id": request["message_id"],
                                          "result": self.node}))

    async def recv(self):
        return self.inbox.pop(0)


def opener(server):
    @asynccontextmanager
    async def connect(url):
        assert url == "ws://nas:5580/ws"
        yield server
    return connect


def collect(store, server=None, now=NOW, cfg=CFG):
    air.ensure_tables(store)
    return asyncio.run(air.collect(cfg, store, connect=opener(server or FakeServer()), now=now))


def test_the_sensors_values_in_the_cards_units(store):
    state = collect(store)

    assert (state.temperature, state.humidity, state.co2, state.pm25) == (23.0, 46, 391, 3)
    assert (state.quality, state.level, state.room, state.available) == (
        "Good", "fresh", "Living room", True)


def test_only_the_node_is_asked_for_read_only(store):
    server = FakeServer(noise=True)
    collect(store, server)
    assert [(m["command"], m["args"]) for m in server.sent] == [("get_node", {"node_id": 1})]


def test_the_co2_words():
    assert [air.level(v) for v in (None, 420, 799, 800, 1200, 1201)] == [
        None, "fresh", "fresh", "stuffy", "stuffy", "open_window"]


def test_missing_values_stay_empty(store):
    state = collect(store, FakeServer(node={"node_id": 1, "attributes": {"1/1026/0": 1999}}))
    assert (state.temperature, state.co2, state.level, state.history) == (20.0, None, None, [])


def test_the_outside_temperature_comes_from_buienradar(store):
    store.put_cache("weather", {"as_of": NOW.isoformat(), "temperature": 9.6})
    assert collect(store).outside == 10


def test_a_matter_error_fails_the_run(store):
    with pytest.raises(RuntimeError, match="Node 1 does not exist"):
        collect(store, FakeServer(error="Node 1 does not exist"))


def test_co2_is_kept_every_five_minutes_and_shown_for_eight_hours(store):
    for minutes in range(0, 9 * 60 + 1, 1):  # a reading every minute for 9 hours
        node = json.loads(json.dumps(NODE))
        node["attributes"]["1/1037/0"] = 400 + minutes
        state = collect(store, FakeServer(node=node), now=NOW + timedelta(minutes=minutes))

    history = state.history
    assert len(history) == 8 * 12 + 1  # every 5 minutes, both ends included
    assert history[-1].co2 == 400 + 9 * 60
    assert history[0].at == NOW + timedelta(hours=1)


def test_samples_older_than_a_day_go(store):
    collect(store)
    collect(store, now=NOW + timedelta(hours=25))
    with store.connect() as conn:
        assert conn.execute("SELECT COUNT(*) AS n FROM air_sample").fetchone()["n"] == 1


def test_switched_off_without_a_matter_server():
    assert air.settings({})["enabled"] is False
    assert air.settings({"air": {"matter": "", "node": 1}})["enabled"] is False
    assert air.settings(CFG)["enabled"] is True


def test_the_api_serves_the_last_reading(store):
    main.app.state.store = store
    client = TestClient(main.app)
    assert client.get("/api/air").status_code == 503
    store.put_cache(air.CACHE_KEY, collect(store).model_dump(mode="json"))
    body = client.get("/api/air").json()
    assert (body["co2"], body["level"], body["stale"]) == (391, "fresh", False)
