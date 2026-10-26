"""The Now panel's run screens (plan.md M28, step 4): A the last run, B the week against the
plan, C the next session. The hub paints each one's picture (app/paint_run.py and the rest)
and places the words here; for A the panel also runs a light along the route, from `path`.

When they show (decided 2026-10-26): A for two days after a run, B every turn while there is
a plan or a run this week, C on the day before a session and on the day until it is run.
"""

from __future__ import annotations

import math
from datetime import UTC, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from . import paint_streets, running
from .desk_pieces import absent, caps, label
from .panel_text import latin1
from .sources import runs, streets
from .store import Store

# A: where the route is drawn (the painter and the light share it).
ROUTE_BOX = (60, 320, 660, 690)
PATH_POINTS = 64
# B: the week's columns.
WEEK_LEFT, WEEK_WIDTH, WEEK_TOP, WEEK_BOTTOM = 36, 648, 250, 600
# C: the session's blocks.
BLOCKS_BOX = (36, 300, 684, 520)

# The clock font's advance per glyph, in pixels (panels/firmware/main/fonts/instrument_clock.c,
# adv_w / 16), so the unit can follow a number set in it.
CLOCK_ADVANCE = {",": 39.75, "-": 74.9, "0": 100.6, "1": 58.4, "2": 82.6, "3": 86.6, "4": 91.1,
                 "5": 86.7, "6": 91.1, "7": 81.9, "8": 88.5, "9": 92.25, ":": 39.75}


def km(metres: float) -> str:
    """"7,3": one decimal with a comma, as the hub writes it."""
    return f"{metres / 1000:.1f}".replace(".", ",")


def pace(seconds_per_km: float) -> str:
    s = round(seconds_per_km)
    return f"{s // 60}:{s % 60:02d}"


def clock(seconds: float) -> str:
    s = round(seconds)
    h, m = divmod(s // 60, 60)
    return f"{h}:{m:02d}:{s % 60:02d}" if h else f"{m}:{s % 60:02d}"


def project(points: list[list[float | None]], box: tuple[int, int, int, int],
            ) -> list[tuple[float, float]]:
    """Latitude and longitude fitted into `box` (x1, y1, x2, y2), north up, as in the web's
    lib/running.ts."""
    if not points:
        return []
    lats = [p[0] for p in points]
    mid = (min(lats) + max(lats)) / 2
    squeeze = math.cos(math.radians(mid))
    xs = [p[1] * squeeze for p in points]
    ys = [-p[0] for p in points]
    x1, y1, x2, y2 = box
    w, h = x2 - x1, y2 - y1
    span_x, span_y = max(max(xs) - min(xs), 1e-9), max(max(ys) - min(ys), 1e-9)
    scale = min(w / span_x, h / span_y)
    dx = x1 + (w - span_x * scale) / 2
    dy = y1 + (h - span_y * scale) / 2
    left, top = min(xs), min(ys)
    return [(dx + (x - left) * scale, dy + (y - top) * scale) for x, y in zip(xs, ys, strict=True)]


def _when(day: str, today: datetime) -> str:
    on = datetime.fromisoformat(day).date()
    if on == today.date():
        return "Today"
    if on == today.date() + timedelta(days=1):
        return "Tomorrow"
    return on.strftime("%A")


def run_screen(store: Store, zone: ZoneInfo, now: datetime) -> dict[str, Any]:
    """A: the last run, for two days after it."""
    view = running.overview(store, zone, now)
    last = view["last"]
    local = now.astimezone(zone)
    if not last:
        return absent("run")
    started = datetime.fromisoformat(last["start"]).astimezone(zone)
    if (local.date() - started.date()).days > 1:
        return absent("run")
    distance = km(last["distance_m"] or 0)
    width = sum(CLOCK_ADVANCE.get(c, 60) for c in distance)
    labels = [
        caps(f"Last run · {started.strftime('%a %-d %b, %H:%M')}", 36, 24, width=460),
        caps(_when(started.date().isoformat(), local), 684, 24, width=200, align="right"),
        label(distance, 36, 66, width=round(width) + 20, font="clock"),
        label("km", 36 + round(width), 146, width=120, font="40", colour="c9c6d6"),
    ]
    stats = [(pace(last["pace_s_per_km"]), "/KM") if last.get("pace_s_per_km") else None,
             (clock(last["duration_s"]), "TIME"),
             (str(round(last["avg_hr"])), "BPM") if last.get("avg_hr") else None,
             (f"{round(last['elevation_up_m'])} m", "CLIMB")
             if last.get("elevation_up_m") else None]
    for i, (value, unit) in enumerate(s for s in stats if s):
        x = 36 + i * 168
        labels += [label(value, x, 214, width=160, font="52"),
                   caps(unit, x, 276, width=160, colour="9a9fb8")]
    if last.get("session"):
        labels.append(label(latin1(f"Runna: {last['session']}"), 684, 72, width=300,
                            align="right", colour="c9c6d6"))
    route = last.get("route") or []
    step = max(1, len(route) / PATH_POINTS)
    picks = ([route[min(len(route) - 1, round(i * step))] for i in range(PATH_POINTS)]
             if route else [])
    path = [[round(x), round(y)] for x, y in project(picks, ROUTE_BOX)]
    kept = streets.fetched_for(store, streets.middle(route)) if route else None
    return {"kind": "run", "stale": False, "present": True, "id": last["id"], "path": path,
            "streets_at": (kept or {}).get("fetched_at"), "labels": labels}


def runweek_screen(store: Store, zone: ZoneInfo, now: datetime) -> dict[str, Any]:
    """B: this week against the plan, while there is a plan or a run this week."""
    view = running.overview(store, zone, now)
    totals = view["totals"]
    if not view["has_plan"] and not totals["week_m"]:
        return absent("runweek")
    today = now.astimezone(zone).date().isoformat()
    labels = [
        caps("Your week · running", 36, 24, width=400),
        label(f"{km(totals['week_m'])} km", 36, 60, width=400, font="52"),
    ]
    if view["has_plan"]:
        labels.append(label(f"of {km(totals['week_planned_m'])} km planned by Runna", 36, 124,
                            width=500, colour="9a9fb8"))
    column = WEEK_WIDTH / 7
    for i, d in enumerate(view["week"]):
        x = round(WEEK_LEFT + column * (i + 0.5))
        letter = datetime.fromisoformat(d["date"]).strftime("%a")[0]
        labels.append(label(letter, x, WEEK_BOTTOM + 16, width=round(column), align="centre",
                            colour="ffffff" if d["date"] == today else "8a8794"))
        if d["done_m"]:
            labels.append(label(km(d["done_m"]), x, WEEK_BOTTOM + 52, width=round(column),
                                align="centre", colour="ffc98f"))
    return {"kind": "runweek", "stale": bool(view["stale"]), "present": True,
            "today": today, "week": [{"planned_m": d["planned_m"], "done_m": d["done_m"],
                                      "runs": d["runs"][:1], "today": d["date"] == today}
                                     for d in view["week"]],
            "labels": labels}


def session_screen(store: Store, zone: ZoneInfo, now: datetime) -> dict[str, Any]:
    """C: the next session, on the day before it and on the day until it is run."""
    view = running.overview(store, zone, now)
    nxt = view["next"]
    local = now.astimezone(zone)
    if not nxt or nxt["date"] > (local.date() + timedelta(days=1)).isoformat():
        return absent("session")
    when = _when(nxt["date"], local) + (f", {nxt['time']}" if nxt.get("time") else "")
    facts = " · ".join(x for x in (f"{km(nxt['distance_m'])} km" if nxt.get("distance_m") else None,
                                   nxt.get("estimate")) if x)
    labels = [
        caps(f"Next run · {when}", 36, 24, width=648),
        label(latin1(nxt["name"]), 36, 64, width=648, font="52", lines=2),
        label(latin1(facts), 36, 200, width=648, font="28", colour="c9c6d6"),
    ]
    for i, step in enumerate(nxt.get("steps", [])[:3]):
        labels.append(label(latin1(step), 36, 576 + i * 36, width=648, colour="9a9fb8"))
    return {"kind": "session", "stale": bool(view["stale"]), "present": True,
            "blocks": nxt.get("blocks", []), "labels": labels}


def streets_screen(store: Store, zone: ZoneInfo, now: datetime) -> dict[str, Any]:
    """D: the year's routes over the town, every turn while there are runs this year."""
    local = now.astimezone(zone)
    since = datetime(local.year, 1, 1, tzinfo=zone).astimezone(UTC).isoformat()
    home, bounds = paint_streets.year_lines(store, since)
    year = home["runs"]
    if not year or bounds is None:
        return absent("streets")
    newest = year[-1]
    today = (newest["id"] if datetime.fromisoformat(newest["start"]).astimezone(zone).date()
             == local.date() else None)
    totals = running.overview(store, zone, now)["totals"]
    total = f"{totals['runs_this_year']} runs · {round(totals['year_m'] / 1000)} km"
    labels = [caps(f"Your streets · {local.year}", 36, 24, width=360),
              caps(total, 684, 24, width=320, align="right")]
    if home["elsewhere"]:
        away = home["elsewhere"]
        labels.append(caps(f"+{away} {'run' if away == 1 else 'runs'} elsewhere", 684, 60,
                           width=320, align="right", colour="9a9fb8"))
    path: list[list[int]] = []
    if today:
        frame = paint_streets.Frame(bounds, paint_streets.MAP_BOX)
        route = runs.routes(store, newest["start"], ids={today})[0]["route"]
        step = max(1, len(route) / PATH_POINTS)
        picks = [route[min(len(route) - 1, round(i * step))] for i in range(PATH_POINTS)]
        path = [[round(x), round(y)] for x, y in (frame.xy(*p) for p in picks)]
    return {"kind": "streets", "stale": False, "present": True, "since": since,
            "count": len(year), "newest": newest["id"], "elsewhere": home["elsewhere"],
            "today_run": today, "path": path,
            "streets_at": (home["streets"] or {}).get("fetched_at"), "labels": labels}
