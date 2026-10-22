from __future__ import annotations

import io
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app import desk, desk_boards, desk_home, main
from app.sources import hue, music, spotify

from .test_hue import CFG, FakeBridge, bulb, collect, spot

AMS = ZoneInfo("Europe/Amsterdam")
NOW = datetime(2026, 10, 20, 21, 0, tzinfo=UTC)
MAC = "e8:f6:0a:e4:42:c8"


def screen(store):
    return desk_home.lights_screen(store, AMS, NOW)


def test_hidden_until_the_lights_are_read(store):
    assert screen(store) == {"kind": "lights", "stale": False, "present": False}


def test_the_living_room_as_tiles_and_the_kitchens_whites(store):
    store.put_cache(hue.CACHE_KEY, collect().model_dump(mode="json"))
    s = screen(store)
    assert s["present"] and s["title"] == "Living room" and s["count"] == "5 of 5 lights on"
    kitchen, ceiling = s["groups"]
    assert (kitchen["name"], kitchen["on"], kitchen["brightness"]) == ("Kitchen spots", True, 77)
    assert kitchen["line"] == "3 lights · 4500 K · 77%" and kitchen["tone"] == "#ffeedd"
    assert ceiling["line"] == "2 lights · 55%" and ceiling["tone"] == desk_home.PLAIN_WHITE
    assert s["whites"]["group"] == "kitchen" and s["whites"]["kelvin"] == 4500
    assert [c["kelvin"] for c in s["whites"]["choices"]] == list(hue.KELVINS)


def test_all_off_says_so(store):
    bridge = FakeBridge(lights=[spot(1, on=False), spot(2, on=False), spot(3, on=False),
                                bulb("Plafondlamp Bank", on=False),
                                bulb("Plafondlamp Tafel", on=False)])
    store.put_cache(hue.CACHE_KEY, collect(bridge).model_dump(mode="json"))
    s = screen(store)
    assert s["count"] == "All lights off" and s["any_on"] is False
    assert s["groups"][0]["line"] == "3 lights · off" and s["whites"]["kelvin"] is None


@pytest.fixture
def panel(store):
    main.app.state.store = store
    main.app.state.config = CFG | {"timezone": "Europe/Amsterdam"}
    main.app.state.hue_bridge = bridge = FakeBridge()
    store.put_cache(hue.CACHE_KEY, collect(bridge).model_dump(mode="json"))
    desk_boards.ensure_tables(store)
    browser = TestClient(main.app, headers={"origin": "http://testserver"})
    browser.get(f"/api/desk/board/{MAC}")
    browser.put(f"/api/settings/desk-boards/{MAC}", json={"panel": "home"})
    key = browser.get(f"/api/desk/board/{MAC}").json()["key"]
    yield TestClient(main.app, headers={"authorization": f"Bearer {key}"}), bridge
    del main.app.state.hue_bridge


def test_a_panel_switches_dims_and_whites_with_its_key(panel):
    client, bridge = panel
    off = client.post("/api/desk/lights/kitchen", json={"on": False}).json()
    assert off["kind"] == "lights" and off["groups"][0]["on"] is False
    warm = client.post("/api/desk/lights/kitchen", json={"kelvin": 2700}).json()
    assert warm["groups"][0]["on"] is True and warm["whites"]["kelvin"] == 2700
    dim = client.post("/api/desk/lights/ceiling", json={"brightness": 20}).json()
    assert dim["groups"][1]["brightness"] == 20
    room = client.post("/api/desk/lights/room", json={"on": False}).json()
    assert room["count"] == "All lights off"
    assert bridge.puts  # the bridge was asked


def test_panel_light_changes_are_checked(panel):
    client, _ = panel
    assert client.post("/api/desk/lights/kitchen", json={}).status_code == 422
    assert client.post("/api/desk/lights/ceiling", json={"kelvin": 2700}).status_code == 422
    assert client.post("/api/desk/lights/hallway", json={"on": True}).status_code == 404
    assert TestClient(main.app).post("/api/desk/lights/kitchen",
                                     json={"on": False}).status_code == 401


# --- music -----------------------------------------------------------------------------

COVER = "0123456789abcdef"
MUSIC = {"as_of": 1792530000.5, "stale": False, "connected": True,
         "default_device": "Apple TV Living Room",
         "playing": {"kind": "track", "title": "Low Tide Static",
                     "subtitle": "Marlow Hayes · Tides",
                     "duration_ms": 214000, "cover": COVER, "colour": "#c06a4a",
                     "state": "playing", "progress_ms": 37000,
                     "device": {"id": "d1", "name": "Apple TV Living Room", "type": "tv",
                                "active": True, "volume": 40, "restricted": False}},
         "devices": [], "last": None,
         "favourites": [{"position": i, "id": f"p{i}", "name": n, "cover": COVER,
                         "colour": "#7c6cf2"}
                        for i, n in enumerate(["Daily Mix", "Focus Flow", "Sunday Morning",
                                               "Liked Songs – mine"])]}


def test_now_playing_and_the_favourites_as_screens():
    playing = desk_home.playing_screen(MUSIC, NOW)
    assert playing["present"] and playing["title"] == "Low Tide Static"
    assert playing["cover"] == f"/api/desk/cover/{COVER}/big" and playing["playing"] is True
    assert (playing["progress_ms"], playing["duration_ms"], playing["at"]) == (37000, 214000,
                                                                               1792530000.5)
    assert playing["device"] == "Apple TV Living Room"
    favourites = desk_home.music_screen(MUSIC)
    assert [f["name"] for f in favourites["favourites"]][-1] == "Liked Songs - mine"
    assert favourites["favourites"][0]["cover"] == f"/api/desk/cover/{COVER}/tile"
    assert favourites["last"] == "Now playing: Low Tide Static · Marlow Hayes · Tides"
    assert favourites["favourites"][0]["thumb"] == f"/api/desk/cover/{COVER}/thumb"
    assert (favourites["last_heading"], favourites["last_title"], favourites["last_subtitle"]) == (
        "Now playing", "Low Tide Static", "Marlow Hayes · Tides")
    assert favourites["last_cover"] == f"/api/desk/cover/{COVER}/thumb"


def test_nothing_playing_leaves_the_favourites_and_what_played_last():
    quiet = MUSIC | {"playing": None, "last": {"title": "Old Song", "subtitle": "Someone"}}
    assert desk_home.playing_screen(quiet, NOW)["present"] is False
    assert desk_home.music_screen(quiet)["last"] == "Last played: Old Song · Someone"
    assert desk_home.music_screen(quiet)["device"] == "Apple TV Living Room"
    last = desk_home.music_screen(quiet)
    assert (last["last_heading"], last["last_title"], last["last_subtitle"]) == (
        "Last played", "Old Song", "Someone")
    assert last["last_cover"] is None
    never = desk_home.music_screen(MUSIC | {"playing": None})
    assert (never["last"], never["last_heading"], never["last_title"]) == ("", "", "")
    assert desk_home.music_screen(None)["present"] is False
    assert desk_home.music_screen(quiet | {"connected": False})["present"] is False


def test_music_comes_first_and_last_on_home(store):
    kinds = [s["kind"] for s in desk.answer({"timezone": "Europe/Amsterdam"}, store, "home", NOW,
                                            music=MUSIC)["screens"]]
    assert kinds == ["playing", "lights", "air", "laundry", "apple", "music"]


@pytest.fixture
def music_panel(panel, store, monkeypatch):
    client, _ = panel
    main.app.state.config = main.app.state.config | {"music": {"client_id": "bench"}}
    spotify.ensure_tables(store)
    out = io.BytesIO()
    Image.new("RGB", (300, 300), (190, 100, 70)).save(out, "WEBP")
    with store.connect() as conn:
        conn.execute("INSERT INTO music_cover (key, url, image, colour) VALUES (?, ?, ?, ?)",
                     (COVER, "https://i.scdn.co/image/x", out.getvalue(), "#be6446"))
    calls = []

    async def control(cfg, store, action):
        calls.append(action)

    async def play_favourite(cfg, store, position, **kw):
        calls.append(f"favourite {position}")
        return "d1"

    async def state(cfg, store):
        return MUSIC

    monkeypatch.setattr(music, "control", control)
    monkeypatch.setattr(music, "play_favourite", play_favourite)
    monkeypatch.setattr(music, "state", state)
    return client, calls


def test_the_home_board_gets_its_music_and_can_play_with_its_key(music_panel):
    client, calls = music_panel
    kinds = [s["kind"] for s in client.get(f"/api/desk/board/{MAC}").json()["screens"]]
    assert kinds == ["playing", "lights", "air", "laundry", "apple", "music"]
    assert client.post("/api/desk/music/pause").json() == {"ok": True}
    assert client.post("/api/desk/music/favourite/2").json() == {"ok": True}
    assert calls == ["pause", "favourite 2"]
    assert client.post("/api/desk/music/louder").status_code == 422
    assert TestClient(main.app).post("/api/desk/music/pause").status_code == 401


def test_covers_are_small_jpegs_of_the_stored_ones(music_panel):
    client, _ = music_panel
    big = client.get(f"/api/desk/cover/{COVER}/big")
    assert big.status_code == 200 and big.headers["content-type"] == "image/jpeg"
    with Image.open(io.BytesIO(big.content)) as image:
        assert image.size == (288, 288) and not image.info.get("progressive")
    with Image.open(io.BytesIO(client.get(f"/api/desk/cover/{COVER}/tile").content)) as image:
        assert image.size == (320, 256)
    with Image.open(io.BytesIO(client.get(f"/api/desk/cover/{COVER}/thumb").content)) as image:
        assert image.size == (96, 96)
    assert client.get("/api/desk/cover/ffffffffffffffff/big").status_code == 404
    assert client.get("/api/desk/cover/not-a-key/big").status_code == 404



# --- laundry ---------------------------------------------------------------------------


def machine(kind, state, **fields):
    return {"id": kind, "name": kind, "kind": kind, "state": state, "online": True,
            "program": fields.get("program"), "remaining_minutes": fields.get("remaining"),
            "total_minutes": fields.get("total"), "ready_at": fields.get("ready_at"),
            "done_at": fields.get("done_at"), "door_open": False, "error": fields.get("error")}


def put_laundry(store, *machines, showing=True):
    store.put_cache("laundry", {"as_of": NOW.isoformat(), "stale": False,
                                "machines": list(machines), "showing": showing})


def test_laundry_only_while_a_machine_runs_or_is_done(store):
    assert desk_home.laundry_screen(store, AMS, NOW)["present"] is False
    put_laundry(store, machine("washer", "idle"), machine("dryer", "idle"), showing=False)
    assert desk_home.laundry_screen(store, AMS, NOW)["present"] is False


def test_a_running_washer_and_a_finished_dryer(store):
    put_laundry(store,
                machine("washer", "running", program="Cotton 40°", remaining=38, total=95,
                        ready_at="2026-10-21T08:52:00+00:00"),
                machine("dryer", "done", done_at="2026-10-21T07:41:00+00:00"))
    s = desk_home.laundry_screen(store, AMS, NOW)
    washer, dryer = s["machines"]
    assert (s["headline"], s["headline_colour"]) == ("Done", "#3fb97f")
    assert (washer["name"], washer["minutes"], washer["progress"]) == ("Washer", 38, 600)
    assert (washer["line"], washer["status"]) == ("Cotton 40°", "Ready at 10:52")
    assert (dryer["line"], dryer["status"], dryer["progress"]) == ("Done at 09:41", "Take it out",
                                                                   1000)
    assert dryer["colour"] == "#3fb97f" and dryer["minutes"] is None


def test_an_error_needs_a_look(store):
    put_laundry(store, machine("washer", "error", error="F13", program="Wool"),
                machine("dryer", "running", remaining=10, total=60))
    s = desk_home.laundry_screen(store, AMS, NOW)
    assert s["headline"] == "Needs a look"
    assert (s["machines"][0]["line"], s["machines"][0]["status"]) == ("See the manual", "Error F13")



# --- Apple devices ---------------------------------------------------------------------


def device(kind, online=True):
    return {"id": kind, "name": kind, "kind": kind, "online": online, "offline_since": None,
            "thread": True}


def test_the_apple_devices_as_rooms(store):
    assert desk_home.apple_screen(store, AMS, NOW)["present"] is False
    store.put_cache("apple", {"as_of": NOW.isoformat(), "stale": False, "rooms": [
        {"id": "lr", "name": "Living room", "devices": [device("homepod"), device("tv")],
         "playing": {"state": "playing", "media": "music", "title": "Glass Harbour",
                     "subtitle": "Ines Vale", "app": "Music", "device": "tv", "artwork": False}},
        {"id": "bd", "name": "Bedroom", "devices": [device("tv"), device("homepod_mini")],
         "playing": None},
        {"id": "bt", "name": "Bathroom", "devices": [device("homepod_mini", online=False)],
         "playing": None}]})
    s = desk_home.apple_screen(store, AMS, NOW)
    assert (s["headline"], s["headline_colour"]) == ("1 offline", "#e0a23b")
    living, bedroom, bathroom = s["rooms"]
    assert living["glow"] == "#9c8ffb" and bedroom["glow"] is None
    assert bathroom["devices"] == [{"kind": "homepod_mini", "online": False}]
    assert s["playing"] == {"title": "Glass Harbour · Ines Vale",
                            "where": "Living room · playing · Music", "colour": "#9c8ffb"}


AIR = {"as_of": NOW.isoformat(), "stale": False, "room": "Living room", "available": True,
       "temperature": 22.9, "humidity": 47, "co2": 1000, "pm25": 2, "quality": "Good",
       "level": "stuffy", "outside": 10,
       "history": [{"at": NOW.isoformat(), "co2": 400 + i} for i in range(120)]}


def test_the_air_screen_is_ready_to_draw(store):
    store.put_cache("air", AIR)

    screen = desk_home.air_screen(store, ZoneInfo("Europe/Amsterdam"), NOW)

    assert {k: v for k, v in screen.items() if k != "history"} == {
        "kind": "air", "stale": False, "present": True, "room": "Living room",
        "outside": "Outside 10°", "temperature": "22,9°", "humidity": "47%", "pm25": "2",
        "quality": "Good", "co2": 1000, "ring": 375, "word": "Getting stuffy", "colour": "#e0a23b"}
    assert screen["history"] == [400 + i for i in range(23, 120)]  # the last 97, 8 hours


def test_the_air_screen_without_a_reading_yet(store):
    zone = ZoneInfo("Europe/Amsterdam")
    empty = {"kind": "air", "stale": False, "present": False}
    assert desk_home.air_screen(store, zone, NOW) == empty
    store.put_cache("air", {**AIR, "temperature": None, "co2": None, "level": None})
    assert desk_home.air_screen(store, zone, NOW)["present"] is False


def test_an_unanswering_sensor_marks_the_air_screen_stale(store):
    store.put_cache("air", {**AIR, "available": False, "outside": None, "co2": 2600})
    screen = desk_home.air_screen(store, ZoneInfo("Europe/Amsterdam"), NOW)
    assert (screen["stale"], screen["outside"], screen["ring"]) == (True, "", 1000)

