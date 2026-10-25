"""The Now panel's clock screen (plan.md M20): the time, the weather in English,
the next sunset or sunrise, a backdrop in the colour of the sky outside, and
the next two hours of rain as bars along the bottom, only when rain is due.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Literal
from zoneinfo import ZoneInfo

from .sources import weather
from .store import Store

# Below this Buienradar's forecast is drizzle at most: counted as dry (as on Home).
WET_MM = 0.1

Sky = Literal["clear", "partly", "cloudy", "fog", "rain", "thunder", "snow"]

# Buienradar describes the weather in Dutch, from a small set of phrases. The
# first keyword found decides (the more specific ones come first); a phrase
# without one stays as Buienradar wrote it.
WORDS: list[tuple[str, str, Sky]] = [
    ("onweer", "Thunderstorms", "thunder"),
    ("hagel", "Hail", "rain"),
    ("ijzel", "Freezing rain", "rain"),
    ("winterse neerslag", "Sleet", "snow"),
    ("lichte sneeuw", "Light snow", "snow"),
    ("sneeuw", "Snow", "snow"),
    ("motregen", "Drizzle", "rain"),
    ("lichte regen", "Light rain", "rain"),
    ("zware regen", "Heavy rain", "rain"),
    ("regen", "Rain", "rain"),
    ("droog na", "Dry after showers", "partly"),
    ("bui", "Showers", "rain"),
    ("dichte mist", "Thick fog", "fog"),
    ("mist", "Fog", "fog"),
    ("nevel", "Haze", "fog"),
    ("zwaar bewolkt", "Overcast", "cloudy"),
    ("half bewolkt", "Partly cloudy", "partly"),
    ("licht bewolkt", "A few clouds", "partly"),
    ("opklaringen", "Clouds and clear spells", "partly"),
    ("bewolkt", "Cloudy", "cloudy"),
    ("zonnig", "Sunny", "clear"),
    ("helder", "Clear", "clear"),
]

TWILIGHT = timedelta(minutes=40)  # either side of sunrise and sunset

# The backdrop's colour and strength (0 to 255): by the light outside, then by the weather.
SKY_COLOURS: dict[str, dict[str, tuple[str, int]]] = {
    "day": {"clear": ("5f97e0", 100), "partly": ("7d98c4", 95), "cloudy": ("8d97ab", 80),
            "fog": ("a3a7b0", 75), "rain": ("4f74b0", 105), "thunder": ("5a4f9a", 110),
            "snow": ("c8d4e8", 80)},
    "dawn": {"clear": ("b46eaa", 110), "partly": ("b46eaa", 100), "other": ("8a7f9e", 90)},
    "dusk": {"clear": ("d8825a", 110), "partly": ("d8825a", 100), "other": ("9a7f8a", 90)},
    "night": {"clear": ("463caa", 120), "other": ("463caa", 100)},
}


def condition(description: str | None) -> tuple[str, Sky | None]:
    """Buienradar's Dutch description in English, and the kind of sky it is."""
    if not description:
        return "", None
    lowered = description.lower()
    for word, english, sky in WORDS:
        if word in lowered:
            return english, sky
    return description, None


def _local(value: str | None, zone: ZoneInfo) -> datetime | None:
    """A cached time in `zone`; one without an offset is already local there
    (as Buienradar writes them), never the machine's own time zone."""
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    return parsed.astimezone(zone) if parsed.tzinfo else parsed.replace(tzinfo=zone)


def _phase(now: datetime, sunrise: datetime | None, sunset: datetime | None) -> str:
    """Day, dawn, dusk or night: from the sun times, else from the hour."""
    if sunrise is None or sunset is None:
        hour = now.hour
        if hour >= 21 or hour < 6:
            return "night"
        return "dawn" if hour < 9 else "day" if hour < 17 else "dusk"
    # The feed has today's times; tomorrow's differ by a minute or two.
    rise = sunrise.replace(year=now.year, month=now.month, day=now.day)
    down = sunset.replace(year=now.year, month=now.month, day=now.day)
    if abs(now - rise) <= TWILIGHT:
        return "dawn"
    if abs(now - down) <= TWILIGHT:
        return "dusk"
    return "day" if rise < now < down else "night"


def sky(now: datetime, sunrise: datetime | None, sunset: datetime | None,
        kind: Sky | None) -> dict[str, Any]:
    """The backdrop's colour (hex, no #) and opacity for the sky outside now."""
    colours = SKY_COLOURS[_phase(now, sunrise, sunset)]
    colour, opacity = colours.get(kind or "partly") or colours["other"]
    return {"colour": colour, "opacity": opacity}


def sun(now: datetime, sunrise: datetime | None, sunset: datetime | None) -> str:
    """The next sunset in the day, else the next sunrise: "Sunset 18:41"."""
    if sunrise is None or sunset is None:
        return ""
    rise = sunrise.replace(year=now.year, month=now.month, day=now.day)
    down = sunset.replace(year=now.year, month=now.month, day=now.day)
    if rise <= now < down:
        return f"Sunset {down:%H:%M}"
    return f"Sunrise {rise:%H:%M}"  # after sunset: tomorrow's, within a minute or two


# The Horizon clock (chosen 2026-10-23): the sky from the zenith down to the horizon, by the
# light outside and the weather (clear, some clouds, or overcast, which takes in fog, rain,
# thunder and snow). Hex without #.
HORIZON_SKIES: dict[str, dict[str, tuple[str, str, str]]] = {
    "day": {"clear": ("0d1d40", "2a5aa8", "6f9fe0"), "partly": ("0f1b36", "2f4f8a", "7b97c8"),
            "overcast": ("10141d", "2c3446", "5f6a80")},
    "dawn": {"clear": ("1a1030", "5a3a6e", "d08a8a"), "partly": ("181028", "4e3a62", "b88a8e"),
             "overcast": ("14121a", "3c3444", "7a6670")},
    "dusk": {"clear": ("1a1030", "5a2d52", "d07a4a"), "partly": ("181028", "4e2d4c", "b47458"),
             "overcast": ("16121c", "443848", "8a6a6a")},
    "night": {"clear": ("05060f", "0d1230", "1b2350"), "partly": ("05060f", "0d1230", "1b2350"),
              "overcast": ("06070c", "10131f", "1e2433")},
}
# A new moon, and the length of a lunar month: the moon's phase from the date alone.
NEW_MOON = datetime(2000, 1, 6, 18, 14, tzinfo=ZoneInfo("UTC"))
LUNAR_DAYS = 29.530588853


def moon_phase(now: datetime) -> float:
    """0 at new moon, 0.5 at full moon, towards 1 at the next new moon."""
    return ((now - NEW_MOON).total_seconds() / 86400 / LUNAR_DAYS) % 1


def horizon(now: datetime, sunrise: datetime | None, sunset: datetime | None,
            kind: Sky | None) -> dict[str, Any]:
    """The Horizon clock's sky: three colours, the sun or the moon and how far along its
    arc (0 to 1000), the moon's phase (0 new, 500 full), and whether stars show."""
    phase = _phase(now, sunrise, sunset)
    group = kind if kind in ("clear", "partly") else "partly" if kind is None else "overcast"
    top, mid, low = HORIZON_SKIES[phase][group]
    body, at = ("sun" if 6 <= now.hour < 18 else "moon"), 500
    rise = down = None
    if sunrise is not None and sunset is not None:
        rise = sunrise.replace(year=now.year, month=now.month, day=now.day)
        down = sunset.replace(year=now.year, month=now.month, day=now.day)
        if rise <= now <= down:
            body, start, end = "sun", rise, down
        elif now > down:  # the evening: the night runs to tomorrow's sunrise
            body, start, end = "moon", down, rise + timedelta(days=1)
        else:  # before sunrise: the night began at yesterday's sunset
            body, start, end = "moon", down - timedelta(days=1), rise
        at = round(1000 * (now - start) / (end - start))
    return {
        "top": top, "mid": mid, "low": low,
        "body": body, "at": max(0, min(1000, at)),
        "moon": round(moon_phase(now) * 1000),
        "veiled": group == "overcast",  # the sun or moon behind clouds: dimmer
        "weather": kind,  # the kind of sky, for the painted background's clouds
        "stars": phase == "night" and group != "overcast",
        "rise": f"{rise:%H:%M}" if rise else "",
        "set": f"{down:%H:%M}" if down else "",
    }


def rain_line(points: list[dict[str, Any]], zone: ZoneInfo) -> str:
    """One line on the next two hours: when it starts or stops, and for how long."""
    if not points:
        return "No rain forecast available"

    def wet(p: dict[str, Any]) -> bool:
        return p["mm_per_hour"] >= WET_MM

    def at(p: dict[str, Any]) -> datetime:
        return datetime.fromisoformat(p["at"]).astimezone(zone)

    if not any(wet(p) for p in points):
        return f"Dry until at least {at(points[-1]):%H:%M}"
    if wet(points[0]):
        dry = next((p for p in points if not wet(p)), None)
        return f"Rain until about {at(dry):%H:%M}" if dry else "Rain for the next 2 hours"
    first = next(i for i, p in enumerate(points) if wet(p))
    dry = next((p for p in points[first:] if not wet(p)), None)
    if dry is None:
        return f"Rain from {at(points[first]):%H:%M}"
    minutes = round((at(dry) - at(points[first])).total_seconds() / 60)
    return f"Rain from {at(points[first]):%H:%M}, about {minutes} min"


def rain_axis(points: list[dict[str, Any]], zone: ZoneInfo) -> list[str]:
    """The labels under the bars: now, and the clock an hour and two hours on."""
    if not points:
        return []
    first = datetime.fromisoformat(points[0]["at"]).astimezone(zone)
    return ["Now", f"{first + timedelta(hours=1):%H:%M}", f"{first + timedelta(hours=2):%H:%M}"]


def clock_screen(store: Store, zone: ZoneInfo, now: datetime) -> dict[str, Any]:
    """The Now panel's clock: the time, the weather, and the rain when it is due."""
    w = store.get_cache(weather.CACHE_KEY) or {}
    points = w.get("rain") or []
    temperature = w.get("temperature")
    station = (w.get("station") or "").removeprefix("Meetstation ").strip()
    local = now.astimezone(zone)
    sunrise, sunset = _local(w.get("sunrise"), zone), _local(w.get("sunset"), zone)
    words, kind = condition(w.get("description"))
    return {
        "kind": "clock",
        "stale": bool(w.get("stale")) or not w,
        "place": station or "Buienradar",
        "date": local.strftime("%a %-d %b"),
        "temperature": round(temperature) if temperature is not None else None,
        "description": words,
        "sun": sun(local, sunrise, sunset),
        "sky": sky(local, sunrise, sunset, kind),
        "horizon": horizon(local, sunrise, sunset, kind),
        # One value per five minutes from now, as the bars along the bottom.
        "rain": [round(p["mm_per_hour"], 2) for p in points],
        "rain_axis": rain_axis(points, zone),
        "rain_line": rain_line(points, zone),
        "wet": any(p["mm_per_hour"] >= WET_MM for p in points),
    }
