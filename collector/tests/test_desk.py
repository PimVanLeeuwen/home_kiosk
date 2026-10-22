from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import ANY
from zoneinfo import ZoneInfo

from fastapi.testclient import TestClient

from app import desk, desk_boards, main

ZONE = ZoneInfo("Europe/Amsterdam")
NOW = datetime(2026, 10, 19, 5, 0, tzinfo=UTC)  # 07:00 in Amsterdam, summer time
CFG = {"timezone": "Europe/Amsterdam"}


def rain(*values: float) -> list[dict]:
    return [{"at": (NOW + timedelta(minutes=5 * i)).isoformat(), "mm_per_hour": v}
            for i, v in enumerate(values)]


def weather(points, stale=False) -> dict:
    return {"as_of": NOW.isoformat(), "stale": stale, "station": "Meetstation De Bilt",
            "temperature": 13.6, "description": "Zwaar bewolkt", "rain": points}


def test_the_now_panel_gets_its_clock_and_the_hubs_time(store):
    store.put_cache("weather", weather(rain(0, 0, 1.24, 2.8, 0)))
    store.put_cache("forecast", forecast(dry_day()))

    answer = desk.answer(CFG, store, "now", NOW)

    assert answer["time"] == {"epoch": NOW.timestamp(), "utc_offset": 7200}
    clock, train, calendar, day, news = answer["screens"]
    assert news == {"kind": "headlines", "stale": False, "present": False}
    assert calendar == {"kind": "agenda", "stale": False, "present": False}
    assert train == {"kind": "train", "stale": False, "present": False}
    assert day["kind"] == "day"
    assert clock == {
        "kind": "clock", "stale": False, "place": "De Bilt", "date": "Mon 19 Oct",
        "temperature": 14, "description": "Overcast", "sun": "",
        "sky": {"colour": "8a7f9e", "opacity": 90}, "rain": [0, 0, 1.24, 2.8, 0],
        "rain_axis": ["Now", "08:00", "09:00"], "rain_line": "Rain from 07:10, about 10 min",
        "wet": True}
    assert answer["stale"] is False


def test_winter_time_moves_the_offset(store):
    winter = datetime(2026, 12, 1, 6, 0, tzinfo=UTC)
    assert desk.answer(CFG, store, "now", winter)["time"]["utc_offset"] == 3600


def test_stale_or_missing_weather_marks_the_screen(store):
    assert desk.answer(CFG, store, "now", NOW)["screens"][0]["stale"] is True
    store.put_cache("weather", weather(rain(0), stale=True))
    answer = desk.answer(CFG, store, "now", NOW)
    assert answer["stale"] is True and answer["screens"][0]["temperature"] == 14


def hours(temps: dict[int, float] | None = None, rain_at: dict[int, int] | None = None) -> list:
    temps, rain_at = temps or {}, rain_at or {}
    return [{"hour": h, "temperature": temps.get(h, 10 + (5 if 12 <= h <= 17 else 0)),
             "rain_chance": rain_at.get(h, 0)} for h in range(24)]


def dry_day(date="2026-10-19", **kw) -> dict:
    return {"date": date, "high": 15.4, "low": 9.4, "sunrise": "08:08", "sunset": "18:36",
            "hours": hours(**kw)}


def forecast(*days, stale=False) -> dict:
    return {"as_of": NOW.isoformat(), "stale": stale, "days": list(days)}


def test_the_day_view_from_six_to_midnight(store):
    store.put_cache("forecast", forecast(dry_day(temps={16: 15.4}),
                                         dry_day("2026-10-20", temps={14: 12.2})))

    day = desk.day_screen(store, ZONE, NOW)  # 07:00

    assert (day["title"], day["high"], day["low"], day["stale"]) == ("Your day", 15, 9, False)
    assert len(day["temperatures"]) == 19 and len(day["rain"]) == 19
    assert (day["sunrise_minute"], day["sunset_minute"], day["now_minute"]) == (488, 1116, 420)
    assert (day["lead"], day["rest"]) == ("Dry for the rest of the day,",
                                          "15° at its warmest around 16:00.")
    assert day["credit"] == "Open-Meteo"


def test_late_in_the_evening_it_shows_tomorrow(store):
    store.put_cache("forecast", forecast(dry_day(), dry_day("2026-10-20")))
    evening = datetime(2026, 10, 19, 18, 30, tzinfo=UTC)  # 20:30 in Amsterdam

    day = desk.day_screen(store, ZONE, evening)

    assert (day["title"], day["now_minute"], day["lead"]) == ("Tomorrow", None, "Dry all day,")


def test_the_sentence_follows_the_rain():
    wet = hours(rain_at={14: 60, 15: 80, 16: 55, 17: 20})
    assert desk.day_sentence(wet, 9) == ("Rain likely from 14:00,", "dry again from 17:00.")
    assert desk.day_sentence(wet, 14) == ("Rain likely now,", "dry again from 17:00.")
    late = hours(rain_at={22: 70, 23: 90})
    assert desk.day_sentence(late, 9) == ("Rain likely from 22:00,", "until the end of the day.")
    maybe = hours(rain_at={11: 35, 12: 45})
    assert desk.day_sentence(maybe, 9) == ("A chance of showers around 12:00,", "45% at most.")
    assert desk.day_sentence(hours(), 19) == ("Dry for the rest of the day,",
                                              "cooling to 10° tonight.")


def test_no_forecast_yet_is_a_stale_day(store):
    day = desk.day_screen(store, ZONE, NOW)
    assert (day["present"], day["stale"]) == (False, True)


def test_the_route_and_its_panel_names(store):
    main.app.state.store = store
    main.app.state.config = CFG
    client = TestClient(main.app)

    assert client.get("/api/desk/test").json()["screens"][0]["kind"] == "clock"
    home = [s["kind"] for s in client.get("/api/desk/home").json()["screens"]]
    assert home == ["playing", "lights", "air", "laundry", "apple", "music"]
    assert client.get("/api/desk/house").json()["screens"] == [
        {"kind": "pipelines", "stale": False, "present": False},
        {"kind": "code", "stale": False, "present": False},
        {"kind": "sites", "stale": False, "present": False},
        {"kind": "services", "stale": False, "present": False},
        {"kind": "tailnet", "stale": False, "present": False},
        {"kind": "movers", "stale": False, "present": False},
        {"kind": "alerts", "stale": False, "present": True, "title": "ALERTS",
         "status": "NONE OPEN", "tone": "ok",
         "quiet": ANY}]  # no data yet
    assert client.get("/api/desk/home").json()["rotate"] is True  # nothing plays, lights unknown
    assert client.get("/api/desk/kitchen").status_code == 422


MAC = "e8:f6:0a:e4:42:b0"
SAME_ORIGIN = {"origin": "http://testserver"}


def board_client(store) -> TestClient:
    main.app.state.store = store
    main.app.state.config = CFG
    desk_boards.ensure_tables(store)
    return TestClient(main.app, headers=SAME_ORIGIN)


def test_an_unknown_board_is_noted_and_asked_to_be_assigned(store):
    client = board_client(store)

    answer = client.get(f"/api/desk/board/{MAC.upper()}", params={"firmware": "v1"}).json()

    assert answer["name"] is None and answer["board"] == MAC
    assert answer["screens"] == [desk.board_screen(MAC, *desk.UNASSIGNED)]
    assert "epoch" in answer["time"]
    [seen] = client.get("/api/settings/desk-boards").json()
    assert seen["mac"] == MAC and seen["panel"] is None and seen["firmware"] == "v1"


def test_an_assigned_board_gets_its_panels_screens(store):
    client = board_client(store)
    client.get(f"/api/desk/board/{MAC}")

    boards = client.put(f"/api/settings/desk-boards/{MAC}", json={"panel": "now"}).json()

    assert boards[0]["panel"] == "now"
    answer = client.get(f"/api/desk/board/{MAC}").json()
    assert answer["name"] == "now"
    kinds = [s["kind"] for s in answer["screens"]]
    assert kinds == ["clock", "train", "agenda", "day", "headlines"]


def test_a_panel_without_screens_says_so_on_its_board(store):
    client = board_client(store)
    client.get(f"/api/desk/board/{MAC}")
    client.put(f"/api/settings/desk-boards/{MAC}", json={"panel": "home"})

    screens = client.get(f"/api/desk/board/{MAC}").json()["screens"]

    assert [s["kind"] for s in screens] == [
        "playing", "lights", "air", "laundry", "apple", "music", "board"]
    screen = screens[-1]
    assert screen["title"] == "Home panel" and screen["hint"] == "Nothing to show yet."
    assert screen["mac"] == MAC


def test_a_panel_has_one_board(store):
    client = board_client(store)
    other = "e8:f6:0a:e4:42:c8"
    client.get(f"/api/desk/board/{MAC}")
    client.get(f"/api/desk/board/{other}")
    client.put(f"/api/settings/desk-boards/{MAC}", json={"panel": "home"})

    boards = client.put(f"/api/settings/desk-boards/{other}", json={"panel": "home"}).json()

    assert {b["mac"]: b["panel"] for b in boards} == {MAC: None, other: "home"}
    boards = client.put(f"/api/settings/desk-boards/{other}", json={"panel": None}).json()
    assert {b["mac"]: b["panel"] for b in boards} == {MAC: None, other: None}


def test_boards_are_checked_at_the_boundary(store):
    client = board_client(store)
    assert client.get("/api/desk/board/not-a-mac").status_code == 422
    assert client.get(f"/api/desk/board/{MAC}", params={"firmware": "x" * 41}).status_code == 422
    assert client.put(f"/api/settings/desk-boards/{MAC}", json={"panel": "now"}).status_code == 404
    client.get(f"/api/desk/board/{MAC}")
    kitchen = client.put(f"/api/settings/desk-boards/{MAC}", json={"panel": "kitchen"})
    assert kitchen.status_code == 422
    # Another website cannot assign boards from the owner's browser.
    elsewhere = TestClient(main.app, headers={"origin": "https://example.com"})
    refused = elsewhere.put(f"/api/settings/desk-boards/{MAC}", json={"panel": "now"})
    assert refused.status_code == 403


def test_a_forgotten_board_comes_back_unassigned(store):
    client = board_client(store)
    client.get(f"/api/desk/board/{MAC}")
    client.put(f"/api/settings/desk-boards/{MAC}", json={"panel": "now"})

    assert client.delete(f"/api/settings/desk-boards/{MAC}").json() == []

    assert client.get(f"/api/desk/board/{MAC}").json()["name"] is None
    assert client.get("/api/settings/desk-boards").json()[0]["panel"] is None


def test_a_visit_updates_last_seen_and_firmware(store):
    desk_boards.ensure_tables(store)
    first = datetime(2026, 10, 19, 10, 0, tzinfo=UTC)
    assert desk_boards.check_in(store, MAC, "v1", first).panel is None
    desk_boards.check_in(store, MAC, "v2", first + timedelta(minutes=1))

    [board] = desk_boards.boards(store)
    assert board.first_seen == first and board.last_seen == first + timedelta(minutes=1)
    assert board.firmware == "v2"


def test_update_now_goes_out_once_with_the_next_answer(store):
    client = board_client(store)
    client.get(f"/api/desk/board/{MAC}")
    assert "update" not in client.get(f"/api/desk/board/{MAC}").json()

    [board] = client.post(f"/api/settings/desk-boards/{MAC}/update", json={}).json()

    assert board["update_requested"] is True
    assert client.get(f"/api/desk/board/{MAC}").json()["update"] is True
    assert "update" not in client.get(f"/api/desk/board/{MAC}").json()
    assert client.get("/api/settings/desk-boards").json()[0]["update_requested"] is False
    assert client.post("/api/settings/desk-boards/e8:f6:0a:e4:42:ff/update",
                       json={}).status_code == 404


def test_an_older_board_table_gets_the_update_column(store):
    with store.connect() as conn:
        conn.execute("CREATE TABLE desk_board (mac TEXT PRIMARY KEY, panel TEXT,"
                     " first_seen TEXT NOT NULL, last_seen TEXT NOT NULL,"
                     " firmware TEXT NOT NULL DEFAULT '')")
    desk_boards.ensure_tables(store)
    desk_boards.check_in(store, MAC, "v1")
    assert desk_boards.boards(store)[0].update_requested is False


def lights(*on: bool, stale: bool = False) -> dict:
    return {"as_of": NOW.isoformat(), "stale": stale, "room": "Living room", "groups": [
        {"id": "kitchen", "name": "Kitchen spots", "kind": "ambiance", "on": any(on),
         "brightness": 80, "kelvin": 3000,
         "lights": [{"id": f"l{i}", "name": f"L{i}", "on": x, "brightness": 80, "kelvin": 3000,
                     "reachable": True} for i, x in enumerate(on)]}]}


def test_the_panels_dim_while_every_living_room_light_is_off(store):
    assert desk.answer(CFG, store, "now", NOW)["dim"] is False  # no lights known: stay bright
    store.put_cache("lights", lights(True, False))
    assert desk.answer(CFG, store, "now", NOW)["dim"] is False
    store.put_cache("lights", lights(False, False))
    assert desk.answer(CFG, store, "home", NOW)["dim"] is True
    store.put_cache("lights", lights(False, False, stale=True))
    assert desk.answer(CFG, store, "now", NOW)["dim"] is False  # cannot tell: stay bright


def test_a_panel_with_nothing_to_show_yet_shows_its_board_screen(store):
    answer = desk.answer(CFG, store, "home", NOW, board=MAC)  # no lights read yet
    kinds = [s["kind"] for s in answer["screens"]]
    assert kinds == ["playing", "lights", "air", "laundry", "apple", "music", "board"]
    assert answer["screens"][-1]["title"] == "Home panel"


PLAYING = {"as_of": NOW.timestamp(), "playing": {"title": "Song", "state": "playing"}}
PAUSED = {"as_of": NOW.timestamp(), "playing": {"title": "Song", "state": "paused"}}


ALL = ["playing", "lights", "air", "laundry", "apple", "music"]


def home(store, music=None):
    out = desk.answer(CFG, store, "home", NOW, music=music)
    return [s["kind"] for s in out["screens"]], out["rotate"]


def test_home_rotates_while_nothing_plays_and_a_light_is_on(store):
    store.put_cache("lights", lights(True, False))
    assert home(store) == (ALL, True)
    assert home(store, PAUSED)[1] is True  # a paused song turns along with the rest


def test_home_stays_on_now_playing_while_music_plays(store):
    store.put_cache("lights", lights(True, False))
    assert home(store, PLAYING) == (ALL, False)
    store.put_cache("lights", lights(False, False))  # music wins over the lights being off
    assert home(store, PLAYING) == (ALL, False)


def test_home_shows_only_the_lights_while_they_are_all_off(store):
    store.put_cache("lights", lights(False, False))
    assert home(store) == (["lights"], False)
    assert home(store, PAUSED) == (["lights"], False)


def test_the_other_panels_keep_turning(store):
    store.put_cache("lights", lights(False, False))
    assert desk.answer(CFG, store, "now", NOW)["rotate"] is True

