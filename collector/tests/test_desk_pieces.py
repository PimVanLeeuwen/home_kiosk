from __future__ import annotations

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

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
