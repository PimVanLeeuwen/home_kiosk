from __future__ import annotations

import io
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app import (
    desk_backgrounds,
    main,
    paint_agenda,
    paint_apple,
    paint_clock,
    paint_headlines,
    paint_laundry,
)

LOCAL = datetime(2026, 10, 25, 17, 44, tzinfo=ZoneInfo("Europe/Amsterdam"))


@pytest.fixture
def client(store):
    main.app.state.store = store
    main.app.state.config = {}
    return TestClient(main.app)


def clock(**horizon):
    sky = {"top": "0f1b36", "mid": "2f4f8a", "low": "7b97c8", "body": "sun", "at": 612,
           "moon": 620, "veiled": False, "stars": False, "weather": "partly"} | horizon
    return {"kind": "clock", "stale": False, "horizon": sky, "rain": [0.0, 0.4, 1.2],
            "wet": True}


def attached(store, screen, local=LOCAL):
    desk_backgrounds.attach(store, [screen], local)
    return screen.get("background")


def test_a_clock_gets_a_background_that_changes_only_with_what_it_shows(store):
    first = attached(store, clock())
    assert first.startswith("/api/desk/background/") and len(first.rsplit("/", 1)[1]) == 16

    # The sun moves in steps of five thousandths of its arc: a little later is the same.
    assert attached(store, clock(at=611)) == first
    assert attached(store, clock(at=630)) != first
    # The clouds drift every three minutes.
    assert attached(store, clock(), LOCAL.replace(minute=43)) == first
    assert attached(store, clock(), LOCAL.replace(minute=45)) != first
    assert attached(store, clock(weather="rain")) != first


def test_screens_without_a_painter_or_a_sky_get_none(store):
    other = {"kind": "agenda", "stale": False}
    assert attached(store, other) is None
    assert attached(store, {"kind": "clock", "stale": True}) is None


def test_only_the_newest_few_are_kept(store):
    for at in range(0, 1000, 50):
        attached(store, clock(at=at))
    with store.connect() as conn:
        assert conn.execute("SELECT COUNT(*) FROM desk_background").fetchone()[0] <= (
            desk_backgrounds.KEEP)


def test_the_picture_is_a_baseline_jpeg_the_panel_can_decode(store):
    key = attached(store, clock()).rsplit("/", 1)[1]

    data = desk_backgrounds.picture(store, key)

    with Image.open(io.BytesIO(data)) as image:
        assert image.format == "JPEG" and image.size == (720, 720)
        assert not image.info.get("progressive")
    assert len(data) < 160 * 1024  # the panel's largest picture (pictures.c)
    assert desk_backgrounds.picture(store, key) == data  # painted once, then kept
    assert desk_backgrounds.picture(store, "0" * 16) is None


def test_every_sky_paints(store):
    for body, weather, stars in (("sun", "clear", False), ("moon", "clear", True),
                                 ("moon", "cloudy", False), ("sun", "thunder", False)):
        data = paint_clock.inputs(clock(body=body, weather=weather, stars=stars), LOCAL)
        assert paint_clock.paint_clock(data).size == (720, 720)


def test_the_route(client, store):
    key = attached(store, clock()).rsplit("/", 1)[1]

    answer = client.get(f"/api/desk/background/{key}")

    assert answer.status_code == 200 and answer.headers["content-type"] == "image/jpeg"
    assert client.get("/api/desk/background/" + "0" * 16).status_code == 404
    assert client.get("/api/desk/background/not-a-key").status_code == 404


def day(**over):
    return {"kind": "day", "stale": False, "present": True, "sunrise_minute": 439,
            "sunset_minute": 1044, "temperatures": [8, 9, 11, 13, 12, 10] + [9] * 13,
            "now_minute": 1100} | over


def agenda(now_ts, **over):
    events = [{"color": "#e6965a", "start_at": now_ts - 600, "end_at": now_ts + 3000},
              {"color": "#6aa8f0", "start_at": now_ts + 3600, "end_at": now_ts + 5400}]
    return {"kind": "agenda", "stale": False, "present": True, "events": events} | over


def test_day_paints_its_nights_and_changes_only_with_the_forecast(store):
    first = attached(store, day())
    assert first and attached(store, day(), LOCAL.replace(hour=21)) == first  # not the clock
    assert attached(store, day(sunset_minute=1050)) != first
    assert attached(store, {"kind": "day", "stale": True, "present": False}) is None
    data = desk_backgrounds.picture(store, first.rsplit("/", 1)[1])
    with Image.open(io.BytesIO(data)) as image:
        assert image.size == (720, 720)


def test_the_calendar_glows_in_the_colour_of_what_is_on(store):
    now = LOCAL.timestamp()
    on = paint_agenda.inputs(agenda(now), LOCAL)
    assert on == {"focus": "#e6965a", "after": "#6aa8f0", "on": True}
    later = paint_agenda.inputs(agenda(now), LOCAL + timedelta(minutes=50))
    assert later == {"focus": "#6aa8f0", "after": None, "on": False}
    assert paint_agenda.inputs(agenda(now, events=[]), LOCAL)["focus"] is None
    assert paint_agenda.paint_agenda(on).size == (720, 720)


def test_headlines_paint_the_lead_picture_with_its_glass(store, monkeypatch):
    out = io.BytesIO()
    Image.new("RGB", (900, 500), (40, 120, 200)).save(out, "WEBP")
    monkeypatch.setattr(paint_headlines.headlines, "picture",
                        lambda s, article, size: out.getvalue() if article == "a1" else None)
    def screen(story, picture=True):
        return {"kind": "headlines", "stale": False, "present": True,
                "stories": [{"id": story, "picture": f"/api/desk/picture/{story}/lead"
                             if picture else None}]}

    key = attached(store, screen("a1")).rsplit("/", 1)[1]

    with Image.open(io.BytesIO(desk_backgrounds.picture(store, key))) as image:
        assert image.size == (720, 720)
        assert image.getpixel((360, 120))[2] > 120   # the picture, up top
        assert max(image.getpixel((360, 690))) < 12   # black under it, for the rows
    assert attached(store, screen("a2", picture=False)) is None
    # Its picture gone from the hub: nothing to paint, so nothing to serve.
    gone = attached(store, screen("a3")).rsplit("/", 1)[1]
    assert desk_backgrounds.picture(store, gone) is None


def machine(name, state):
    return {"name": name, "state": state, "colour": "#3fb97f" if state == "done" else "#9c8ffb"}


def test_laundry_shows_the_one_machine_that_is_on_alone():
    assert paint_laundry.layout([machine("Washer", "running"), machine("Dryer", "idle")]) == 0
    assert paint_laundry.layout([machine("Washer", "idle"), machine("Dryer", "done")]) == 1
    assert paint_laundry.layout([machine("Washer", "running"), machine("Dryer", "done")]) == -1
    assert paint_laundry.layout([machine("Washer", "running")]) == 0
    one = paint_laundry.inputs({"present": True, "machines": [machine("Washer", "running"),
                                                               machine("Dryer", "idle")]}, LOCAL)
    assert one == {"which": 0, "count": 2, "colours": [paint_laundry.RUNNING]}
    assert paint_laundry.paint_laundry(one).size == (720, 720)
    both = paint_laundry.inputs({"present": True, "machines": [machine("Washer", "running"),
                                                                machine("Dryer", "done")]}, LOCAL)
    assert both["which"] == -1 and both["colours"] == [paint_laundry.RUNNING, "#3fb97f"]
    assert paint_laundry.paint_laundry(both).size == (720, 720)


def test_air_and_apple_glow_only_with_what_changes(store):
    air = {"kind": "air", "stale": False, "present": True, "colour": "#3fb97f", "co2": 600}
    first = attached(store, air)
    assert attached(store, {**air, "co2": 640}) == first
    assert attached(store, {**air, "colour": "#e0a23b"}) != first
    rooms = [{"name": "Living room", "glow": "#5aa9ff"}, {"name": "Bedroom", "glow": None}]
    apple = paint_apple.inputs({"present": True, "rooms": rooms}, LOCAL)
    assert apple == {"count": 2, "glows": ["#5aa9ff", None]}
    assert paint_apple.paint_apple(apple).size == (720, 720)


def test_now_playing_washes_in_its_covers_colours(store):
    from app.sources import spotify
    spotify.ensure_tables(store)
    out = io.BytesIO()
    Image.new("RGB", (300, 300), (220, 60, 120)).save(out, "WEBP")
    with store.connect() as conn:
        conn.execute("INSERT INTO music_cover (key, url, image) VALUES ('c1', 'u', ?)",
                     (out.getvalue(),))
    screen = {"kind": "playing", "stale": False, "present": True,
              "cover": "/api/desk/cover/c1/big"}

    key = attached(store, screen).rsplit("/", 1)[1]

    with Image.open(io.BytesIO(desk_backgrounds.picture(store, key))) as image:
        r, g, b = image.getpixel((360, 120))
        assert r > g and r > 40  # the cover's red, washed over the top
    nothing = {"kind": "playing", "stale": False, "present": False}
    assert attached(store, nothing) is None
