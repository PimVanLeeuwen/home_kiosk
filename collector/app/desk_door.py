"""The Door panel's today view (plan.md M32): the date, the temperature now and tonight,
the rain over the next two hours, today's open reminders, the birthdays of the coming
week and the wind, as ready-to-draw values. The panel draws the clock and words the rain
("Dry for 28 min, then rain until 09:25") on its own clock from the spell's start and
end, so the countdown runs between answers.

Reminder titles and names are personal data: served to the panel, never logged.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from . import reminders
from .desk_clock import WET_MM, condition
from .panel_text import latin1
from .sources import birthdays, forecast, weather
from .store import Store

MAX_REMINDERS = 5
MAX_BIRTHDAYS = 4
RAIN_STEP = 300  # seconds between Buienradar's points
TONIGHT_FROM, TONIGHT_UNTIL = 18, 6  # the hours "tonight" spans
# Buienradar's wind directions are Dutch: O is east, Z south.
COMPASS = str.maketrans({"O": "E", "Z": "S"})


def _tonight(store: Store, local: datetime) -> int | None:
    """The lowest temperature from 18:00 (or now, when later) to 06:00 tomorrow."""
    days = (store.get_cache(forecast.CACHE_KEY) or {}).get("days") or []
    by_date = {d["date"]: d for d in days}
    today = by_date.get(local.date().isoformat()) or {}
    tomorrow = by_date.get((local.date() + timedelta(days=1)).isoformat()) or {}
    start = max(TONIGHT_FROM, local.hour)
    temps = [h["temperature"] for h in today.get("hours") or [] if h["hour"] >= start]
    temps += [h["temperature"] for h in tomorrow.get("hours") or [] if h["hour"] <= TONIGHT_UNTIL]
    return round(min(temps)) if temps else None


def rain(points: list[dict[str, Any]]) -> dict[str, Any]:
    """The bars and the first spell: when it starts (0: it rains now) and when it is dry
    again (0: not within the two hours), as seconds since 1970."""
    if not points:
        return {"rain": [], "rain_from": 0, "wet_from": 0, "wet_until": 0, "wet": False}
    at = [round(datetime.fromisoformat(p["at"]).timestamp()) for p in points]
    wet = [p["mm_per_hour"] >= WET_MM for p in points]
    first = next((i for i, w in enumerate(wet) if w), None)
    dry = next((i for i in range(first, len(wet)) if not wet[i]), None) if first is not None \
        else None
    return {
        "rain": [round(p["mm_per_hour"], 2) for p in points],
        "rain_from": at[0],
        "wet": first is not None,
        "wet_from": at[first] if first not in (None, 0) else 0,
        "wet_until": at[dry] if dry is not None else 0,
    }


def _wind(w: dict[str, Any]) -> str:
    bft, towards = w.get("wind_bft"), (w.get("wind_direction") or "").upper()
    if bft is None:
        return ""
    where = towards.translate(COMPASS) if towards.isalpha() and len(towards) <= 3 else ""
    return f"Wind {bft} Bft from {where}" if where else f"Wind {bft} Bft"


def _when(days: int, date_iso: str) -> str:
    if days == 0:
        return "today"
    if days == 1:
        return "tomorrow"
    return datetime.fromisoformat(date_iso).strftime("%a")


def door_screen(store: Store, zone: ZoneInfo, now: datetime) -> dict[str, Any]:
    local = now.astimezone(zone)
    w = store.get_cache(weather.CACHE_KEY) or {}
    temperature = w.get("temperature")
    words, _sky = condition(w.get("description"))
    reminders.ensure_tables(store)
    due = [r for r in reminders.today(store, local.date()) if not r["done"]]
    cached = store.get_cache(birthdays.CACHE_KEY)
    week = birthdays.upcoming(cached, local.date()).birthdays if cached else []
    tonight = _tonight(store, local)
    return {
        "kind": "door",
        "stale": bool(w.get("stale")) or not w,
        "present": True,
        "date": local.strftime("%A %-d %B"),
        "temperature": round(temperature) if temperature is not None else None,
        "description": words,
        "tonight": f"Tonight {tonight}°" if tonight is not None else "",
        **rain(w.get("rain") or []),
        "rain_step": RAIN_STEP,
        "wind": _wind(w),
        "reminders": [{"title": latin1(r["title"]), "at": r["at"] or ""}
                      for r in due[:MAX_REMINDERS]],
        "more_reminders": max(0, len(due) - MAX_REMINDERS),
        "birthdays": [{"name": latin1(b.name), "when": _when(b.days, b.date),
                       "turns": b.turns or 0, "today": b.days == 0}
                      for b in week[:MAX_BIRTHDAYS]],
    }
