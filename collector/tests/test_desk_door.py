from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

from PIL import Image

from app import desk, desk_door, paint_door, reminders
from app.sources import birthdays, forecast, weather

AMS = ZoneInfo("Europe/Amsterdam")
CFG = {"timezone": "Europe/Amsterdam"}
NOW = datetime(2026, 11, 4, 7, 12, tzinfo=UTC)  # 08:12 in Amsterdam, a Wednesday


def points(*mm: float, start: datetime = NOW) -> list[dict]:
    return [{"at": (start + timedelta(minutes=5 * i)).isoformat(), "mm_per_hour": m}
            for i, m in enumerate(mm)]


def stamp(minutes: int) -> int:
    return round((NOW + timedelta(minutes=minutes)).timestamp())


def test_the_rain_spell_starts_and_ends_on_its_points():
    rain = lambda p: desk_door.rain(p, NOW)  # noqa: E731
    soon = rain(points(0, 0, 0, 0.4, 1.2, 0.5, 0, 0))
    assert (soon["wet"], soon["wet_from"], soon["wet_until"]) == (True, stamp(15), stamp(30))
    now = rain(points(0.3, 0.2, 0, 0))
    assert (now["wet_from"], now["wet_until"]) == (0, stamp(10))  # it rains now
    on = rain(points(0, 0.3, 0.2))
    assert (on["wet_from"], on["wet_until"]) == (stamp(5), 0)  # not dry within two hours
    dry = rain(points(0, 0, 0))
    assert (dry["wet"], dry["wet_from"], dry["wet_until"], dry["rain"]) == (False, 0, 0, [0, 0, 0])
    assert rain([])["rain"] == []


def test_rain_that_has_already_fallen_is_left_out():
    """Buienradar's answer starts up to minutes ago: the shower of 20 minutes ago is over."""
    old = desk_door.rain(points(1.0, 1.0, 1.0, 0, 0, 0, 0.6, 0, start=NOW - timedelta(minutes=20)),
                         NOW)
    assert (old["rain_from"], old["wet_from"], old["wet_until"]) == (stamp(0), stamp(10),
                                                                     stamp(15))
    assert old["rain"] == [0, 0, 0.6, 0]


def setup(store):
    store.put_cache(weather.CACHE_KEY, {
        "as_of": NOW.isoformat(), "stale": False, "temperature": 8.6,
        "description": "Lichte regen", "wind_bft": 4, "wind_direction": "ZW",
        "rain": points(0, 0, 0.4)})
    store.put_cache(forecast.CACHE_KEY, {"as_of": NOW.isoformat(), "stale": False, "days": [
        {"date": "2026-11-04", "high": 11, "low": 5,
         "hours": [{"hour": h, "temperature": 12 - h / 4, "rain_chance": 0} for h in range(24)]},
        {"date": "2026-11-05", "high": 10, "low": 3,
         "hours": [{"hour": h, "temperature": 3.4 + h, "rain_chance": 0} for h in range(24)]}]})
    store.put_cache(birthdays.CACHE_KEY, {"as_of": NOW.isoformat(), "stale": False, "people": [
        {"name": "Anna", "month": 11, "day": 4, "year": 1992},
        {"name": "Bram", "month": 11, "day": 6, "year": None}]})
    reminders.ensure_tables(store)
    done = reminders.add(store, reminders.Draft(title="Plants", start=date(2026, 11, 4)))
    reminders.add(store, reminders.Draft(title="Bins out", start=date(2026, 11, 4), at="07:30"))
    reminders.set_done(store, done.id, date(2026, 11, 4), True)


def test_the_today_view_has_the_weather_the_open_reminders_and_the_birthdays(store):
    setup(store)
    s = desk_door.door_screen(store, AMS, NOW)

    assert (s["date"], s["temperature"], s["description"], s["tonight"]) == (
        "Wednesday 4 November", 9, "Light rain", "Tonight 3°")  # 3.4° at midnight
    assert s["wind"] == "Wind 4 Bft from SW"
    assert (s["wet"], s["wet_from"], s["rain_step"]) == (True, stamp(10), 300)
    assert s["reminders"] == [{"title": "Bins out", "at": "07:30"}]  # Plants is ticked off
    assert s["birthdays"] == [{"name": "Anna", "when": "today", "turns": 34, "today": True},
                              {"name": "Bram", "when": "Fri", "turns": 0, "today": False}]


def test_the_today_view_without_any_data_still_shows(store):
    reminders.ensure_tables(store)
    s = desk_door.door_screen(store, AMS, NOW)
    assert (s["present"], s["stale"], s["temperature"], s["tonight"], s["wind"]) == (
        True, True, None, "", "")
    assert (s["reminders"], s["birthdays"], s["rain"]) == ([], [], [])


def test_the_door_panel_answer_fits_and_has_its_background(store):
    setup(store)
    out = desk.answer(CFG, store, "door", NOW)
    [screen] = out["screens"]
    assert screen["background"].startswith("/api/desk/background/")
    assert desk.size(out) < 4096


def test_the_background_paints_its_lights():
    for part in ("morning", "day", "evening", "night"):
        image = paint_door.paint_door({"part": part, "wet": True, "birthday": True})
        assert isinstance(image, Image.Image) and image.size == (720, 720)
    assert paint_door.inputs({"present": False}, datetime(2026, 11, 4, 8, tzinfo=AMS)) is None
    assert paint_door.inputs({"present": True, "wet": False, "birthdays": [{"today": True}]},
                             datetime(2026, 11, 4, 21, tzinfo=AMS)) == {
        "part": "evening", "wet": False, "birthday": True}
