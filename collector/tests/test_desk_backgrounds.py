from __future__ import annotations

import io
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app import desk_backgrounds, main, paint_clock

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
