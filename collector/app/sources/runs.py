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


def settings(cfg: dict[str, Any]) -> dict[str, Any]:
    key = ((cfg.get("running") or {}).get("key") or "").strip()
    return {"enabled": bool(key), "key": key}


def ensure_tables(store: Store) -> None:
    with store.connect() as conn:
        conn.execute(TABLES)


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
            conn.execute(
                "INSERT OR REPLACE INTO run (id, start, end, name, indoor, duration_s, distance_m, "
                "elevation_up_m, elevation_down_m, energy_kcal, avg_hr, max_hr, temperature_c, "
                "humidity, route, heart, received_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, "
                "?, ?, ?, ?, ?)",
                (run["id"], run["start"], run["end"], run["name"], int(run["indoor"]),
                 run["duration_s"], run["distance_m"], run["elevation_up_m"],
                 run["elevation_down_m"], run["energy_kcal"], run["avg_hr"], run["max_hr"],
                 run["temperature_c"], run["humidity"], json.dumps(run["route"]),
                 json.dumps(run["heart"]), received_at))
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


def simplified(route: list[list[float]], most: int) -> list[list[float]]:
    """At most `most` points of the route, evenly spaced, the ends kept: [latitude, longitude]."""
    if len(route) <= most:
        return [[p[0], p[1]] for p in route]
    step = (len(route) - 1) / (most - 1)
    return [[route[round(i * step)][0], route[round(i * step)][1]] for i in range(most)]


def _summary(row: Any) -> dict[str, Any]:
    distance = row["distance_m"]
    return {
        "id": row["id"], "start": row["start"], "name": row["name"], "indoor": bool(row["indoor"]),
        "duration_s": row["duration_s"], "distance_m": distance,
        "pace_s_per_km": round(row["duration_s"] / (distance / 1000)) if distance else None,
        "elevation_up_m": row["elevation_up_m"], "avg_hr": row["avg_hr"],
        "max_hr": row["max_hr"], "energy_kcal": row["energy_kcal"],
        "temperature_c": row["temperature_c"],
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
        "route": simplified(route, points),
        "splits": splits(route),
        "heart": json.loads(row["heart"]),
    }
