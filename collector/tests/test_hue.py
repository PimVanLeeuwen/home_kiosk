from __future__ import annotations

import asyncio
import copy
import json
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from fastapi.testclient import TestClient

from app import main
from app.sources import hue

NOW = datetime(2026, 10, 14, 19, 0, tzinfo=UTC)
CFG = {"hue": {
    "bridge": "10.0.0.59", "bridge_id": "001788FFFE123456", "key": "secret-key",
    "room": "Living room",
    "groups": [
        {"id": "kitchen", "name": "Kitchen spots", "lights": ["Keuken 1", "Keuken 2", "Keuken 3"]},
        {"id": "ceiling", "name": "Ceiling lamps",
         "lights": ["Plafondlamp Bank", "Plafondlamp Tafel"]},
    ]}}
SCHEMA = {"mirek_minimum": 153, "mirek_maximum": 454}


def spot(n: int, on=True, brightness=77.08, mirek=222) -> dict:
    return {"id": f"spot-{n}", "type": "light",
            "owner": {"rid": f"dev-spot-{n}", "rtype": "device"},
            "metadata": {"name": f"Keuken {n}", "archetype": "spot_bulb"},
            "on": {"on": on}, "dimming": {"brightness": brightness, "min_dim_level": 0.2},
            "color_temperature": {"mirek": mirek, "mirek_valid": True, "mirek_schema": SCHEMA}}


def bulb(name: str, on=True, brightness=55.0) -> dict:
    rid = name.split()[-1].lower()
    return {"id": f"bulb-{rid}", "type": "light", "owner": {"rid": f"dev-{rid}", "rtype": "device"},
            "metadata": {"name": name, "archetype": "vintage_bulb"},
            "on": {"on": on}, "dimming": {"brightness": brightness}}


OTHER = bulb("Hue filament bulb 1")  # the hallway: never touched


class FakeBridge:
    def __init__(self, lights=None, unreachable=()):
        self.lights = {x["id"]: x for x in (lights or [spot(1), spot(2), spot(3),
                                                       bulb("Plafondlamp Bank"),
                                                       bulb("Plafondlamp Tafel"), OTHER])}
        self.unreachable = set(unreachable)
        self.puts: list[tuple[str, str, dict]] = []

    async def get(self, kind):
        if kind == "light":
            return copy.deepcopy(list(self.lights.values()))
        return [{"id": f"z-{d}", "owner": {"rid": d},
                 "status": "connectivity_issue" if d in self.unreachable else "connected"}
                for d in ("dev-spot-1", "dev-spot-2", "dev-spot-3", "dev-bank", "dev-tafel")]

    async def put(self, kind, rid, body):
        self.puts.append((kind, rid, body))
        light = self.lights[rid]
        if "on" in body:
            light["on"] = body["on"]
        if "dimming" in body:
            light["dimming"]["brightness"] = float(body["dimming"]["brightness"])
        if "color_temperature" in body:
            light["color_temperature"]["mirek"] = body["color_temperature"]["mirek"]


def collect(bridge=None):
    return asyncio.run(hue.collect(CFG, bridge or FakeBridge(), NOW))


# --- reading --------------------------------------------------------------------------


def test_the_living_room_as_two_groups_from_config():
    lights = collect()

    kitchen, ceiling = lights.groups
    assert (lights.room, lights.kelvins) == ("Living room", [2200, 2700, 3500, 4500, 6500])
    assert (kitchen.kind, kitchen.on, kitchen.brightness, kitchen.kelvin) == (
        "ambiance", True, 77, 4500)
    assert [x.name for x in kitchen.lights] == ["Keuken 1", "Keuken 2", "Keuken 3"]
    assert (ceiling.kind, ceiling.brightness, ceiling.kelvin) == ("white", 55, None)
    assert "Hue filament bulb 1" not in lights.model_dump_json()


def test_a_group_is_on_when_any_light_is_and_shows_their_level():
    bridge = FakeBridge([spot(1, on=False, brightness=10), spot(2, brightness=60),
                         spot(3, brightness=40), bulb("Plafondlamp Bank", on=False),
                         bulb("Plafondlamp Tafel", on=False, brightness=30)])

    kitchen, ceiling = collect(bridge).groups

    assert (kitchen.on, kitchen.brightness) == (True, 50)  # of the two that are on
    assert (ceiling.on, ceiling.brightness) == (False, 42)  # the level they had


def test_an_unreachable_light_is_marked():
    kitchen = collect(FakeBridge(unreachable={"dev-spot-2"})).groups[0]

    assert [x.reachable for x in kitchen.lights] == [True, False, True]


def test_kelvin_and_mirek():
    assert [hue.kelvin_of(m) for m in (222, 454, 153, None)] == [4500, 2200, 6500, None]
    assert [hue.mirek_of(k, SCHEMA) for k in hue.KELVINS] == [454, 370, 286, 222, 154]
    assert hue.mirek_of(1800, SCHEMA) == 454  # clamped to what the spot can do


# --- changing -------------------------------------------------------------------------


def change(store, group, bridge, **kw):
    return asyncio.run(hue.change(CFG, store, group, bridge=bridge, **kw))


def test_switching_a_group_touches_only_its_lights_and_returns_the_bridge_state(store):
    bridge = FakeBridge()

    result = change(store, "ceiling", bridge, on=False)

    assert bridge.puts == [("light", "bulb-bank", {"on": {"on": False}}),
                           ("light", "bulb-tafel", {"on": {"on": False}})]
    assert result.groups[1].on is False
    assert store.get_cache(hue.CACHE_KEY)["groups"][1]["on"] is False


def test_dimming_or_a_white_also_switches_on(store):
    bridge = FakeBridge([spot(1, on=False), spot(2, on=False), spot(3, on=False)])

    change(store, "kitchen", bridge, brightness=40, kelvin=2700)

    assert bridge.puts[0] == ("light", "spot-1", {
        "dimming": {"brightness": 40}, "on": {"on": True},
        "color_temperature": {"mirek": 370}})
    assert len(bridge.puts) == 3


def test_lamps_without_whites_refuse_a_white(store):
    with pytest.raises(ValueError):
        change(store, "ceiling", FakeBridge(), kelvin=2700)
    with pytest.raises(KeyError):
        change(store, "hallway", FakeBridge(), on=True)


def test_the_room_switch_leaves_other_rooms_alone(store):
    bridge = FakeBridge()

    asyncio.run(hue.switch_room(CFG, store, False, bridge=bridge))

    assert sorted(rid for _, rid, _ in bridge.puts) == [
        "bulb-bank", "bulb-tafel", "spot-1", "spot-2", "spot-3"]


# --- live -----------------------------------------------------------------------------


def test_events_patch_the_cached_answer():
    payload = collect().model_dump(mode="json")
    later = NOW + timedelta(seconds=5)
    events = [{"type": "update", "data": [
        {"id": "spot-1", "type": "light", "on": {"on": False}},
        {"id": "spot-2", "type": "light", "on": {"on": False}},
        {"id": "spot-3", "type": "light", "dimming": {"brightness": 20.0},
         "color_temperature": {"mirek": 454}},
        {"id": OTHER["id"], "type": "light", "on": {"on": False}},
        {"id": "x", "type": "grouped_light", "on": {"on": False}},
    ]}]

    assert hue.apply_events(payload, events, later) is True

    kitchen = payload["groups"][0]
    assert (kitchen["on"], kitchen["brightness"], kitchen["kelvin"]) == (True, 20, 2200)
    assert payload["as_of"] == later.isoformat()
    assert hue.apply_events(payload, [{"type": "add", "data": []}], later) is False


# --- the bridge itself ----------------------------------------------------------------


def test_the_bridge_sends_the_key_in_a_header_and_names_the_bridge_id():
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append((request.headers["hue-application-key"], request.extensions.get("sni_hostname"),
                     request.url.path))
        return httpx.Response(200, json={"errors": [], "data": [spot(1)]})

    bridge = hue.Bridge(CFG, transport=httpx.MockTransport(handler))
    data = asyncio.run(bridge.get("light"))

    assert data[0]["id"] == "spot-1"
    assert seen == [("secret-key", "001788fffe123456", "/clip/v2/resource/light")]
    assert "secret-key" not in bridge.base


def test_bridge_errors_are_short_and_never_hold_the_key():
    def refuse(request):
        return httpx.Response(403, json={"errors": [{"description": "unauthorized user"}]})

    def unreachable(request):
        problem = {"description": "device (light) is unreachable"}
        return httpx.Response(207, json={"errors": [problem], "data": []})

    with pytest.raises(hue.HueError, match="refused the key") as refused:
        asyncio.run(hue.Bridge(CFG, transport=httpx.MockTransport(refuse)).get("light"))
    with pytest.raises(hue.HueError, match="unreachable"):
        asyncio.run(hue.Bridge(CFG, transport=httpx.MockTransport(unreachable))
                    .put("light", "spot-1", {"on": {"on": True}}))
    assert "secret-key" not in str(refused.value)
    assert hue.reason(httpx.ConnectError("x")) == "The bridge is not reachable"


def test_the_ca_file_holds_signifys_roots():
    assert len(hue.tls_context().get_ca_certs()) == 2


def test_switched_off_without_a_key():
    assert hue.settings(CFG)["enabled"] is True
    assert hue.settings({"hue": CFG["hue"] | {"key": ""}})["enabled"] is False
    assert hue.settings({})["enabled"] is False


# --- the routes -----------------------------------------------------------------------


@pytest.fixture
def client(store):
    main.app.state.store = store
    main.app.state.config = CFG
    main.app.state.hue_bridge = FakeBridge()
    yield TestClient(main.app, headers={"origin": "http://testserver"})
    del main.app.state.hue_bridge


def test_the_routes(client, store):
    assert client.get("/api/lights").status_code == 503
    store.put_cache(hue.CACHE_KEY, collect().model_dump(mode="json"))
    assert client.get("/api/lights").json()["groups"][0]["name"] == "Kitchen spots"

    dimmed = client.put("/api/lights/kitchen", json={"brightness": 30})
    assert dimmed.status_code == 200 and dimmed.json()["groups"][0]["brightness"] == 30
    assert client.post("/api/lights/room", json={"on": False}).json()["groups"][0]["on"] is False


def test_the_routes_refuse_bad_changes(client):
    assert client.put("/api/lights/kitchen", json={}).status_code == 422
    assert client.put("/api/lights/kitchen", json={"kelvin": 3000}).status_code == 422
    assert client.put("/api/lights/kitchen", json={"brightness": 0}).status_code == 422
    assert client.put("/api/lights/ceiling", json={"kelvin": 2700}).status_code == 422
    assert client.put("/api/lights/hallway", json={"on": True}).status_code == 404


def test_writes_need_the_same_origin(client):
    foreign = client.put("/api/lights/kitchen", json={"on": False},
                         headers={"origin": "https://evil.example"})
    assert foreign.status_code == 403


def test_a_bridge_failure_is_a_502_with_a_reason(client):
    class Down(FakeBridge):
        async def get(self, kind):
            raise httpx.ConnectError("no route")

    main.app.state.hue_bridge = Down()
    failed = client.put("/api/lights/kitchen", json={"on": True})
    assert (failed.status_code, failed.json()["detail"]) == (502, "The bridge is not reachable")


def test_reads_the_event_stream():
    message = [{"type": "update", "data": [{"id": "spot-1", "type": "light", "on": {"on": False}}]}]
    stream = f": hi\n\nid: 1:0\ndata: {json.dumps(message)}\n\ndata: not json\n\n"

    def handler(request):
        assert request.url.path == "/eventstream/clip/v2"
        assert request.headers["accept"] == "text/event-stream"
        return httpx.Response(200, text=stream, headers={"content-type": "text/event-stream"})

    async def read():
        bridge = hue.Bridge(CFG, transport=httpx.MockTransport(handler))
        return [events async for events in bridge.events()]

    assert asyncio.run(read()) == [message]
