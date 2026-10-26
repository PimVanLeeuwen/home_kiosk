"""Runs from Apple Health (plan.md M28): the phone's Health Auto Export app posts workouts to
the hub (its REST automation, JSON version 2, routes and workout metrics on), with the key
in `running.key` (NAS-only `RUNS_KEY`) as a bearer token. Only runs are kept, one row each
by Health's id, so a run sent again replaces itself.

Kept on the NAS only: the route (latitude, longitude, altitude, seconds from the start,
speed) and the heart rate by the minute. Routes start at home: they are never logged, never
sent anywhere, and the repo's fixtures use a made-up place.
"""

from __future__ import annotations

import json
import math
from datetime import UTC, datetime
from typing import Any

from ..store import Store

TABLES = """
CREATE TABLE IF NOT EXISTS run (
    id TEXT PRIMARY KEY,
    start TEXT NOT NULL,
    end TEXT NOT NULL,
    name TEXT NOT NULL,
    indoor INTEGER NOT NULL,
    duration_s REAL NOT NULL,
    distance_m REAL,
    elevation_up_m REAL,
    elevation_down_m REAL,
    energy_kcal REAL,
    avg_hr REAL,
    max_hr REAL,
    temperature_c REAL,
    humidity REAL,
    route TEXT NOT NULL,
    heart TEXT NOT NULL,
    received_at TEXT NOT NULL
)
"""

TO_METRES = {"m": 1.0, "km": 1000.0, "ft": 0.3048, "mi": 1609.344, "yd": 0.9144}
# Best efforts: the fastest stretch of this length inside any run, worked out from its route.
BESTS = {"5k": 5000.0, "10k": 10000.0, "half": 21097.5}


def settings(cfg: dict[str, Any]) -> dict[str, Any]:
    key = ((cfg.get("running") or {}).get("key") or "").strip()
    return {"enabled": bool(key), "key": key}


def ensure_tables(store: Store) -> None:
    with store.connect() as conn:
        conn.execute(TABLES)
        # Columns added after the table first shipped (step 3).
        have = {r["name"] for r in conn.execute("PRAGMA table_info(run)").fetchall()}
        for name in BESTS:
            if f"best_{name}_s" not in have:
                conn.execute(f"ALTER TABLE run ADD COLUMN best_{name}_s REAL")
        # Where each run was (step 5): its middle and bounds, so grouping runs by area never
        # reads their routes. Filled by `fill_places` for runs kept before.
        for name in PLACE:
            if name not in have:
                conn.execute(f"ALTER TABLE run ADD COLUMN {name} REAL")
        # Whether the best efforts were looked for: a run whose route has no 5 km in it (GPS
        # cut short) keeps no best, and must not be searched again on every request.
        if "bests_checked" not in have:
            conn.execute("ALTER TABLE run ADD COLUMN bests_checked INTEGER NOT NULL DEFAULT 0")
            conn.execute("UPDATE run SET bests_checked = 1 WHERE best_5k_s IS NOT NULL "
                         "OR distance_m < 5000 OR route = '[]'")


PLACE = ("mid_lat", "mid_lon", "south", "west", "north", "east")


def place(route: list[list[Any]]) -> tuple[float | None, ...]:
    """The route's middle (the mean of its points) and its bounds, or Nones without a route."""
    if not route:
        return (None,) * len(PLACE)
    lats, lons = [p[0] for p in route], [p[1] for p in route]
    return (round(sum(lats) / len(lats), 6), round(sum(lons) / len(lons), 6),
            min(lats), min(lons), max(lats), max(lons))


def is_run(workout: dict[str, Any]) -> bool:
    """Health's running workouts: "Running", "Outdoor Run", "Indoor Run", "Trail Run"."""
    return "run" in str(workout.get("name") or "").lower()


def when(value: str) -> datetime:
    """Health Auto Export's "2026-10-26 07:12:03 +0100"."""
    return datetime.strptime(value, "%Y-%m-%d %H:%M:%S %z")


def _metres(quantity: Any) -> float | None:
    if not isinstance(quantity, dict) or quantity.get("qty") is None:
        return None
    factor = TO_METRES.get(str(quantity.get("units") or "m").lower())
    return round(float(quantity["qty"]) * factor, 1) if factor else None


def _qty(quantity: Any) -> float | None:
    if not isinstance(quantity, dict) or quantity.get("qty") is None:
        return None
    return round(float(quantity["qty"]), 1)


def _celsius(quantity: Any) -> float | None:
    value = _qty(quantity)
    if value is None:
        return None
    return round((value - 32) * 5 / 9, 1) if quantity.get("units") == "degF" else value


def _route(points: list[dict[str, Any]], start: datetime) -> list[list[float]]:
    out = []
    for p in points or []:
        try:
            at = when(p["timestamp"]) if isinstance(p.get("timestamp"), str) else None
            out.append([round(float(p["latitude"]), 6), round(float(p["longitude"]), 6),
                        round(float(p.get("altitude") or 0), 1),
                        round((at - start).total_seconds()) if at else 0,
                        round(float(p.get("speed") or 0), 2)])
        except (KeyError, TypeError, ValueError):
            continue
    return out


def _heart(points: list[dict[str, Any]], start: datetime) -> list[list[float]]:
    out = []
    for p in points or []:
        try:
            at = round((when(p["date"]) - start).total_seconds())
            out.append([at, round(float(p["Avg"]), 1)])
        except (KeyError, TypeError, ValueError):
            continue
    return out


def parse(workout: dict[str, Any]) -> dict[str, Any]:
    """A run as the hub keeps it."""
    start, end = when(workout["start"]), when(workout["end"])
    indoor = workout.get("isIndoor")
    if indoor is None:
        indoor = workout.get("location") == "Indoor"
    return {
        "id": str(workout["id"]),
        "start": start.astimezone(UTC).isoformat(),
        "end": end.astimezone(UTC).isoformat(),
        "name": str(workout.get("name") or "Run"),
        "indoor": bool(indoor),
        "duration_s": float(workout.get("duration") or (end - start).total_seconds()),
        "distance_m": _metres(workout.get("distance")),
        "elevation_up_m": _metres(workout.get("elevationUp")),
        "elevation_down_m": _metres(workout.get("elevationDown")),
        "energy_kcal": _qty(workout.get("activeEnergyBurned")),
        "avg_hr": _qty(workout.get("avgHeartRate")),
        "max_hr": _qty(workout.get("maxHeartRate")),
        "temperature_c": _celsius(workout.get("temperature")),
        "humidity": _qty(workout.get("humidity")),
        "route": _route(workout.get("route") or [], start),
        "heart": _heart(workout.get("heartRateData") or [], start),
    }


def receive(store: Store, body: dict[str, Any], now: datetime | None = None) -> dict[str, int]:
    """Keeps the runs in an export; anything else in it is left alone. Counts only."""
    ensure_tables(store)
    workouts = ((body or {}).get("data") or {}).get("workouts") or []
    received_at = (now or datetime.now(UTC)).isoformat()
    kept = skipped = failed = 0
    with store.connect() as conn:
        for workout in workouts:
            if not isinstance(workout, dict) or not is_run(workout):
                skipped += 1
                continue
            try:
                run = parse(workout)
            except (KeyError, TypeError, ValueError):
                failed += 1
                continue
            bests = [best_effort(run["route"], metres) for metres in BESTS.values()]
            conn.execute(
                "INSERT OR REPLACE INTO run (id, start, end, name, indoor, duration_s, distance_m, "
                "elevation_up_m, elevation_down_m, energy_kcal, avg_hr, max_hr, temperature_c, "
                "humidity, route, heart, received_at, best_5k_s, best_10k_s, best_half_s, "
                f"{', '.join(PLACE)}, bests_checked) "
                f"VALUES ({', '.join('?' * (20 + len(PLACE)))}, 1)",
                (run["id"], run["start"], run["end"], run["name"], int(run["indoor"]),
                 run["duration_s"], run["distance_m"], run["elevation_up_m"],
                 run["elevation_down_m"], run["energy_kcal"], run["avg_hr"], run["max_hr"],
                 run["temperature_c"], run["humidity"], json.dumps(run["route"]),
                 json.dumps(run["heart"]), received_at, *bests, *place(run["route"])))
            kept += 1
    return {"kept": kept, "skipped": skipped, "failed": failed}


# --- reading ----------------------------------------------------------------------------


def _metres_between(a: list[float], b: list[float]) -> float:
    """Haversine, in metres."""
    lat1, lon1, lat2, lon2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = (math.sin((lat2 - lat1) / 2) ** 2
         + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2)
    return 2 * 6_371_000 * math.asin(math.sqrt(h))


def splits(route: list[list[float]]) -> list[dict[str, float]]:
    """Seconds per whole kilometre along the route, and the part kilometre at the end."""
    out: list[dict[str, float]] = []
    done, mark_t, mark_d = 0.0, route[0][3] if route else 0, 0.0
    for a, b in zip(route, route[1:], strict=False):
        step = _metres_between(a, b)
        while done + step >= mark_d + 1000:
            share = (mark_d + 1000 - done) / step if step else 0
            t = a[3] + share * (b[3] - a[3])
            out.append({"km": len(out) + 1, "seconds": round(t - mark_t), "metres": 1000})
            mark_t, mark_d = t, mark_d + 1000
        done += step
    if route and done - mark_d >= 100:
        out.append({"km": len(out) + 1, "seconds": round(route[-1][3] - mark_t),
                    "metres": round(done - mark_d)})
    return out


def best_effort(route: list[list[float]], metres: float) -> float | None:
    """The fewest seconds any stretch of `metres` took along the route, or None when the route
    is shorter. Two pointers over the distance run so far; a stretch a little longer than
    `metres` is scaled down to it."""
    if len(route) < 2:
        return None
    done = [0.0]
    for a, b in zip(route, route[1:], strict=False):
        done.append(done[-1] + _metres_between(a, b))
    if done[-1] < metres:
        return None
    best = None
    i = 0
    for j in range(1, len(route)):
        while done[j] - done[i + 1] >= metres:
            i += 1
        stretch = done[j] - done[i]
        if stretch >= metres and route[j][3] > route[i][3]:
            seconds = (route[j][3] - route[i][3]) * metres / stretch
            best = seconds if best is None else min(best, seconds)
    return round(best) if best is not None else None


SMOOTH = 2  # stretches either side a drawn pace is taken over


def paced(route: list[list[float]], most: int) -> list[list[float | None]]:
    """At most `most` points of the route with the pace (seconds per km) since the point before:
    [latitude, longitude, pace]; the first point has none."""
    if not route:
        return []
    if len(route) <= most:
        picks = list(range(len(route)))
    else:
        step = (len(route) - 1) / (most - 1)
        picks = [round(i * step) for i in range(most)]
    # The pace over a few stretches either side, so GPS jitter does not speckle the line.
    done = [0.0]
    for a, b in zip(route, route[1:], strict=False):
        done.append(done[-1] + _metres_between(a, b))
    out: list[list[float | None]] = [[route[0][0], route[0][1], None]]
    for n in range(1, len(picks)):
        # The same number of stretches everywhere: at the ends the window slides inwards.
        lo, hi = n - SMOOTH, n + SMOOTH
        if lo < 0:
            lo, hi = 0, min(len(picks) - 1, hi - lo)
        if hi > len(picks) - 1:
            lo, hi = max(0, lo - (hi - len(picks) + 1)), len(picks) - 1
        before, after = picks[lo], picks[hi]
        metres = done[after] - done[before]
        seconds = route[after][3] - route[before][3]
        pace = round(seconds / (metres / 1000)) if metres > 1 and seconds > 0 else None
        out.append([route[picks[n]][0], route[picks[n]][1], pace])
    return out


def simplified(route: list[list[float]], most: int) -> list[list[float]]:
    """At most `most` points of the route, evenly spaced, the ends kept: [latitude, longitude]."""
    if len(route) <= most:
        return [[p[0], p[1]] for p in route]
    step = (len(route) - 1) / (most - 1)
    return [[route[round(i * step)][0], route[round(i * step)][1]] for i in range(most)]


SUMMARY = ("id, start, name, indoor, duration_s, distance_m, elevation_up_m, energy_kcal, "
           "avg_hr, max_hr, temperature_c, best_5k_s, best_10k_s, best_half_s")


def _summary(row: Any) -> dict[str, Any]:
    distance = row["distance_m"]
    return {
        "id": row["id"], "start": row["start"], "name": row["name"], "indoor": bool(row["indoor"]),
        "duration_s": row["duration_s"], "distance_m": distance,
        "pace_s_per_km": round(row["duration_s"] / (distance / 1000)) if distance else None,
        "elevation_up_m": row["elevation_up_m"], "avg_hr": row["avg_hr"],
        "max_hr": row["max_hr"], "energy_kcal": row["energy_kcal"],
        "temperature_c": row["temperature_c"],
        "bests": {name: row[f"best_{name}_s"] for name in BESTS},
    }


def latest(store: Store, limit: int = 20) -> list[dict[str, Any]]:
    ensure_tables(store)
    with store.connect() as conn:
        rows = conn.execute("SELECT * FROM run ORDER BY start DESC LIMIT ?", (limit,)).fetchall()
    return [_summary(r) for r in rows]


def one(store: Store, run_id: str, points: int = 400) -> dict[str, Any] | None:
    ensure_tables(store)
    with store.connect() as conn:
        row = conn.execute("SELECT * FROM run WHERE id = ?", (run_id,)).fetchone()
    if row is None:
        return None
    route = json.loads(row["route"])
    return _summary(row) | {
        "route": paced(route, points),
        "splits": splits(route),
        "heart": json.loads(row["heart"]),
    }


def fill_bests(store: Store) -> int:
    """Best efforts for runs kept before they were worked out (step 1 kept no bests): any run
    of 5 km or more with a route and no 5 km best yet. Returns how many were filled."""
    with store.connect() as conn:
        rows = conn.execute("SELECT id, route FROM run WHERE bests_checked = 0").fetchall()
        for row in rows:
            route = json.loads(row["route"])
            bests = [best_effort(route, metres) for metres in BESTS.values()]
            conn.execute("UPDATE run SET best_5k_s = ?, best_10k_s = ?, best_half_s = ?, "
                         "bests_checked = 1 WHERE id = ?", (*bests, row["id"]))
    return len(rows)


def fill_places(store: Store) -> int:
    """Middles and bounds for runs kept before they were stored (step 5). Returns how many."""
    with store.connect() as conn:
        rows = conn.execute("SELECT id, route FROM run WHERE mid_lat IS NULL AND "
                            "route != '[]'").fetchall()
        for row in rows:
            conn.execute(f"UPDATE run SET {' = ?, '.join(PLACE)} = ? WHERE id = ?",
                         (*place(json.loads(row["route"])), row["id"]))
    return len(rows)


def places(store: Store, start: str) -> list[dict[str, Any]]:
    """Where every run with a route from `start` (ISO, UTC) on was, oldest first, without
    reading a route: {id, start, middle: [lat, lon], box: [south, west, north, east]}."""
    ensure_tables(store)
    fill_places(store)
    with store.connect() as conn:
        rows = conn.execute("SELECT id, start, mid_lat, mid_lon, south, west, north, east "
                            "FROM run WHERE start >= ? AND mid_lat IS NOT NULL ORDER BY start",
                            (start,)).fetchall()
    return [{"id": r["id"], "start": r["start"], "middle": [r["mid_lat"], r["mid_lon"]],
             "box": [r["south"], r["west"], r["north"], r["east"]]} for r in rows]


def since(store: Store, start: str) -> list[dict[str, Any]]:
    """Every run from `start` (ISO, UTC) on, newest first, without routes."""
    ensure_tables(store)
    fill_bests(store)
    with store.connect() as conn:
        # Not `*`: the routes are most of each row, and this runs on every panel request.
        rows = conn.execute(f"SELECT {SUMMARY} FROM run WHERE start >= ? ORDER BY start DESC",
                            (start,)).fetchall()
    return [_summary(r) for r in rows]


def routes(store: Store, start: str, points: int = 200,
           ids: set[str] | None = None) -> list[dict[str, Any]]:
    """The routes of every run from `start` (ISO, UTC) on (only `ids`, when given), oldest
    first, thinned to `points`: {id, start, route: [[latitude, longitude], ...]}. Reading routes
    is slow with many runs: only for painting, never on every request."""
    ensure_tables(store)
    with store.connect() as conn:
        rows = conn.execute("SELECT id, start, route FROM run WHERE start >= ? AND route != '[]' "
                            "ORDER BY start", (start,)).fetchall()
    return [{"id": r["id"], "start": r["start"],
             "route": simplified(json.loads(r["route"]), points)}
            for r in rows if ids is None or r["id"] in ids]
