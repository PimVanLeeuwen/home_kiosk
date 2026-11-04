from __future__ import annotations

import io
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from PIL import Image, ImageStat

from app import desk_pieces
from app.sources import weather

ZONE = ZoneInfo("Europe/Amsterdam")


def at(hour, minute=0):
    return datetime(2026, 10, 25, hour, minute, tzinfo=ZONE)


def sky_store(store, description="Licht bewolkt"):
    store.put_cache(weather.CACHE_KEY, {
        "description": description, "temperature": 12, "station": "Meetstation Testdorp",
        "sunrise": "2026-10-25T07:20:00", "sunset": "2026-10-25T17:24:00", "rain": []})
    return store


def night(store, now):
    return desk_pieces.night_screen(store, ZONE, now)["present"]


def test_the_night_sky_after_dark_when_clear(store):
    sky_store(store)
    assert not night(store, at(12).astimezone(UTC))
    assert not night(store, at(17, 30).astimezone(UTC))  # dusk
    assert night(store, at(23).astimezone(UTC))
    sky_store(store, "Zwaar bewolkt")
    assert not night(store, at(23).astimezone(UTC))  # the Clock alone then


def test_the_moon_and_the_constellation_in_words():
    assert desk_pieces.moon_words(0.5) == "Full moon, 100% lit"
    assert desk_pieces.moon_words(0.25) == "First quarter, 50% lit"
    assert desk_pieces.moon_words(0.0) == "New moon, 0% lit"
    assert desk_pieces.constellation(datetime(2026, 12, 1, 22)) == "Orion"
    assert desk_pieces.constellation(datetime(2026, 4, 1, 22)) == "the Big Dipper"
    assert desk_pieces.constellation(datetime(2026, 8, 1, 22)) == "Cassiopeia"


def test_the_radar_only_while_rain_is_coming(store):
    from app.sources import radar
    sky_store(store)
    assert desk_pieces.radar_screen(store, ZONE, at(9).astimezone(UTC))["present"] is False
    w = store.get_cache(weather.CACHE_KEY)
    store.put_cache(weather.CACHE_KEY, w | {"rain": [{"at": "2026-10-26T09:05:00+01:00",
                                                      "mm_per_hour": 1.2}]})
    store.put_cache(radar.CACHE_KEY, {"as_of": "x", "stale": False, "stamp": "202610260805",
                                      "wet": True, "home": [281.5, 312.0]})
    radar.FRAMES.rain = b"rain"
    try:
        screen = desk_pieces.radar_screen(store, ZONE, at(9).astimezone(UTC))
    finally:
        radar.FRAMES.rain = None
    assert screen["present"] and screen["home"] == [281.5, 312.0]
    assert "BUIENRADAR · 09:05" in [label["text"] for label in screen["labels"]]
    assert radar.to_pixel(52.96, 4.76) == (radar.X0 + 4.76 * radar.PX_PER_LON, radar.Y0)


def test_the_tunnel_paints_at_any_distance():
    from app import paint_countdown
    for days_left in (0, 1, 19, 400):
        tunnel = paint_countdown.paint_countdown({"days": days_left, "colour": "#8f80ff"})
        assert tunnel.getpixel(paint_countdown.CORE)[0] > 240  # the day, white-hot


def _rain_png(colour):
    out = io.BytesIO()
    Image.new("RGBA", (500, 512), colour).save(out, "PNG")
    return out.getvalue()


def test_the_radar_draws_its_own_outline_of_the_land():
    from app import paint_radar
    from app.sources import radar

    def middle(lat, lon):  # what the outline has at a place, seen from right above it
        mask = paint_radar._land(list(radar.to_pixel(lat, lon)), (20, 20), (21, 21))
        return mask.getpixel((10, 10))

    assert middle(52.09, 5.12) == 255  # Utrecht: land
    assert middle(52.5, 3.5) == 0      # the North Sea
    assert middle(52.85, 5.35) == 0    # the IJsselmeer: a lake, left out of the land


def test_the_radar_shows_how_hard_it_rains():
    from app import paint_radar
    from app.sources import radar

    light, heavy = (236, 237, 253, 162), (112, 130, 250, 165)  # Buienradar's palest and deepest
    assert paint_radar._field(_rain_png(light)).getpixel((5, 5)) == 40
    assert paint_radar._field(_rain_png(heavy)).getpixel((5, 5)) > 240
    assert paint_radar._field(_rain_png((0, 0, 0, 0))).getpixel((5, 5)) == 0
    home = list(radar.to_pixel(52.09, 5.12))
    seen = {}
    try:
        for name, colour in (("light", light), ("heavy", heavy)):
            radar.FRAMES.rain = _rain_png(colour)
            picture = paint_radar.paint_radar({"stamp": "x", "home": home, "rain": []})
            seen[name] = ImageStat.Stat(picture.convert("L").crop((200, 200, 300, 300))).mean[0]
    finally:
        radar.FRAMES.rain = None
    assert picture.size == (720, 720) and seen["heavy"] > seen["light"] * 1.5


def test_the_weather_page_gets_the_forecast_and_the_radar_only_while_rain_comes(store):
    import io

    from fastapi.testclient import TestClient
    from PIL import Image

    from app import main, paint_radar
    from app.sources import forecast, radar
    main.app.state.store = store
    client = TestClient(main.app)
    assert client.get("/api/forecast").status_code == 503
    store.put_cache(forecast.CACHE_KEY, {"as_of": "x", "stale": False, "days": []})
    assert client.get("/api/forecast").json()["days"] == []

    def png(size, colour):
        out = io.BytesIO()
        Image.new("RGBA", size, colour).save(out, "PNG")
        return out.getvalue()

    store.put_cache(radar.CACHE_KEY, {"as_of": "x", "stale": False, "stamp": "202610261005",
                                      "wet": False, "home": [281.5, 312.0]})
    radar.FRAMES.rain = png((500, 512), (0, 0, 255, 90))
    try:
        assert client.get("/api/radar").json()["wet"] is False
        assert client.get("/api/radar/map").status_code == 404  # dry: no radar
        store.put_cache(radar.CACHE_KEY, store.get_cache(radar.CACHE_KEY) | {"wet": True})
        got = client.get("/api/radar/map")
        assert got.status_code == 200 and got.headers["content-type"] == "image/jpeg"
        with Image.open(io.BytesIO(got.content)) as image:
            assert image.size == paint_radar.WEB_SIZE
    finally:
        radar.FRAMES.rain = None
        paint_radar._web.update(key=None, jpeg=None)
