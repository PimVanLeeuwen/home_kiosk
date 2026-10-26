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


def kinds_present(store, now):
    return [s["kind"] for s in (desk_pieces.sky_screen(store, ZONE, now),
                                desk_pieces.night_screen(store, ZONE, now)) if s["present"]]


def test_the_living_sky_by_day_the_night_sky_after_dark_when_clear(store):
    sky_store(store)
    assert kinds_present(store, at(12).astimezone(UTC)) == ["sky"]
    assert kinds_present(store, at(17, 30).astimezone(UTC)) == ["sky"]  # dusk
    assert kinds_present(store, at(23).astimezone(UTC)) == ["night"]
    sky_store(store, "Zwaar bewolkt")
    assert kinds_present(store, at(23).astimezone(UTC)) == []  # the Clock alone then


def test_what_the_light_does_next():
    rise, down = at(7, 20), at(17, 24)
    assert desk_pieces.next_light(at(6), rise, down) == "Sunrise 07:20"
    assert desk_pieces.next_light(at(12), rise, down) == "Golden hour from 16:24"
    assert desk_pieces.next_light(at(16, 40), rise, down) == "Sunset 17:24"
    assert desk_pieces.next_light(at(17, 40), rise, down) == "Dark from 18:04"
    assert desk_pieces.next_light(at(22), rise, down) == "Sunrise 07:20"
    assert desk_pieces.next_light(at(12), None, None) == ""


def test_the_sky_carries_its_words_and_the_time(store):
    sky_store(store)
    screen = desk_pieces.sky_screen(store, ZONE, at(12).astimezone(UTC))
    texts = [label["text"] for label in screen["labels"]]
    assert texts == ["SUN 25 OCT", "TESTDORP", "Golden hour from 16:24", "12° · A few clouds"]
    assert screen["clock"]["font"] == "clock" and screen["horizon"]["top"]


def test_the_moon_and_the_constellation_in_words():
    assert desk_pieces.moon_words(0.5) == "Full moon, 100% lit"
    assert desk_pieces.moon_words(0.25) == "First quarter, 50% lit"
    assert desk_pieces.moon_words(0.0) == "New moon, 0% lit"
    assert desk_pieces.constellation(datetime(2026, 12, 1, 22)) == "Orion"
    assert desk_pieces.constellation(datetime(2026, 4, 1, 22)) == "the Big Dipper"
    assert desk_pieces.constellation(datetime(2026, 8, 1, 22)) == "Cassiopeia"


def test_the_year_counts_its_days(store):
    screen = desk_pieces.year_screen(store, ZONE, at(12).astimezone(UTC))
    assert (screen["today"], screen["days"]) == (298, 365)
    texts = [label["text"] for label in screen["labels"]]
    assert "298" in texts and "of 365" in texts and "67 days left this year" in texts
    leap = desk_pieces.year_screen(store, ZONE, datetime(2028, 12, 31, 12, tzinfo=UTC))
    assert (leap["today"], leap["days"]) == (366, 366)


def test_the_art_and_the_orbit_always_show(store):
    art = desk_pieces.art_screen(store, ZONE, at(9).astimezone(UTC))
    assert art["present"] and art["season"] == "autumn"
    assert [label["text"] for label in art["labels"]][1] == "NO. 298"
    orbit = desk_pieces.orbit_screen(store, ZONE, at(9).astimezone(UTC))
    assert orbit["present"] and orbit["clock"]["font"] == "28"


def test_the_week_has_seven_columns_with_words_where_the_bars_are(store):
    from datetime import date, timedelta

    from app.sources import countdown, forecast
    days = [{"date": (date(2026, 10, 26) + timedelta(days=i)).isoformat(), "high": 10 + i,
             "low": 4 + i % 3, "sunrise": None, "sunset": None, "hours": [], "code": 61,
             "rain_max": 30 if i == 0 else 10} for i in range(7)]
    store.put_cache(forecast.CACHE_KEY, {"as_of": "x", "stale": False, "days": days})
    store.put_cache(countdown.CACHE_KEY, {"as_of": "x", "stale": False, "events": [],
                                          "per_day": {"2026-10-26": 2},
                                          "per_day_colours": {"2026-10-26": ["#e6965a"]}})
    screen = desk_pieces.week_screen(store, ZONE, at(9).astimezone(UTC))
    texts = [label["text"] for label in screen["labels"]]
    assert "TODAY" in texts and "TUE" in texts and "16°" in texts and "30%" in texts
    assert len(screen["labels"]) == 30 and screen["days"][0]["events"] == ["#e6965a"]
    store.put_cache(forecast.CACHE_KEY, {"as_of": "x", "stale": False, "days": days[:2]})
    assert desk_pieces.week_screen(store, ZONE, at(9).astimezone(UTC))["present"] is False


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


def test_every_weather_paints_in_the_week_and_the_tunnel_at_any_distance():
    from app import paint_countdown, paint_week
    codes = [0, 2, 3, 45, 61, 71, 95]  # sun, partly, cloud, fog, rain, snow, thunder
    days = [{"high": 2 + 2 * i, "low": -2 + i, "code": c, "rain": 60, "events": ["#e6965a"]}
            for i, c in enumerate(codes)]
    assert [paint_week.sky_of(c) for c in codes] == ["sun", "partly", "cloud", "fog", "rain",
                                                     "snow", "thunder"]
    week = paint_week.paint_week({"days": days, "warmest": 14, "coldest": -2})
    assert week.size == (720, 720)
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
