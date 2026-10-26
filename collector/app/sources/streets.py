"""The town's streets under the runs (plan.md M28, step 5): fetched once, when asked in Settings,
from the public Overpass API (OpenStreetMap), for a box round all the runs kept; then drawn from
the hub's own copy. Decided 2026-10-26: the owner accepts that this one request tells Overpass's
servers the area the runs are in; nothing else is sent, and nothing at all after it.

Kept: only the shapes, in three kinds (roads by size, water, parks), positions rounded to about a
metre; no names or other tags.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

import httpx

from ..store import Store

URL = "https://overpass-api.de/api/interpreter"
TIMEOUT_SECONDS = 180
MARGIN = 0.15        # the box grows by this share of its size on every side
MIN_SPAN = 0.02      # degrees: at least a small town's worth round a single run
MAX_SPAN = 0.4       # degrees: never more than a city's worth
MAJOR = {"motorway", "trunk", "primary", "secondary", "tertiary", "motorway_link", "trunk_link",
         "primary_link", "secondary_link", "tertiary_link"}
MINOR = {"residential", "unclassified", "living_street", "service", "pedestrian", "road"}
PATHS = {"footway", "path", "cycleway", "track", "steps", "bridleway"}

TABLE = """
CREATE TABLE IF NOT EXISTS street_map (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    fetched_at TEXT NOT NULL,
    box TEXT NOT NULL,
    shapes TEXT NOT NULL
)
"""


def box_round(points: list[list[float]]) -> tuple[float, float, float, float] | None:
    """South, west, north, east round the points, with a margin; None without points."""
    if not points:
        return None
    lats, lons = [p[0] for p in points], [p[1] for p in points]
    south, north, west, east = min(lats), max(lats), min(lons), max(lons)
    grow_lat = max((north - south) * MARGIN, (MIN_SPAN - (north - south)) / 2, 0)
    grow_lon = max((east - west) * MARGIN, (MIN_SPAN - (east - west)) / 2, 0)
    south, north = south - grow_lat, north + grow_lat
    west, east = west - grow_lon, east + grow_lon
    if north - south > MAX_SPAN or east - west > MAX_SPAN:  # runs far apart: round their middle
        mid_lat, mid_lon = (south + north) / 2, (west + east) / 2
        half = MAX_SPAN / 2
        south, north = mid_lat - half, mid_lat + half
        west, east = mid_lon - half, mid_lon + half
    return round(south, 5), round(west, 5), round(north, 5), round(east, 5)


def query(box: tuple[float, float, float, float]) -> str:
    s, w, n, e = box
    area = f"({s},{w},{n},{e})"
    return (f"[out:json][timeout:{TIMEOUT_SECONDS - 10}];("
            f"way[highway]{area};"
            f"way[waterway~\"^(river|canal|stream)$\"]{area};"
            f"way[natural=water]{area};"
            f"way[leisure=park]{area};way[landuse~\"^(forest|grass|meadow)$\"]{area};"
            f");out geom;")


def kind_of(tags: dict[str, str]) -> str | None:
    highway = tags.get("highway")
    if highway in MAJOR:
        return "major"
    if highway in MINOR:
        return "minor"
    if highway in PATHS:
        return "path"
    if tags.get("waterway") or tags.get("natural") == "water":
        return "water"
    if tags.get("leisure") == "park" or tags.get("landuse") in ("forest", "grass", "meadow"):
        return "park"
    return None


def shapes(answer: dict[str, Any]) -> dict[str, list[list[list[float]]]]:
    """Overpass's ways as lines of [latitude, longitude] by kind."""
    out: dict[str, list[list[list[float]]]] = {"major": [], "minor": [], "path": [], "water": [],
                                               "park": []}
    for element in answer.get("elements") or []:
        kind = kind_of(element.get("tags") or {})
        geometry = element.get("geometry") or []
        if kind and len(geometry) >= 2:
            out[kind].append([[round(g["lat"], 5), round(g["lon"], 5)] for g in geometry])
    return out


def ensure_table(store: Store) -> None:
    with store.connect() as conn:
        conn.execute(TABLE)


def kept(store: Store) -> dict[str, Any] | None:
    ensure_table(store)
    with store.connect() as conn:
        row = conn.execute("SELECT * FROM street_map WHERE id = 1").fetchone()
    if row is None:
        return None
    return {"fetched_at": row["fetched_at"], "box": json.loads(row["box"]),
            "shapes": json.loads(row["shapes"])}


def status(store: Store) -> dict[str, Any]:
    """When they were fetched and how many of each kind, for Settings."""
    found = kept(store)
    if not found:
        return {"fetched_at": None, "counts": {}}
    return {"fetched_at": found["fetched_at"],
            "counts": {k: len(v) for k, v in found["shapes"].items()}}


async def fetch(store: Store, points: list[list[float]], now: datetime | None = None,
                transport: httpx.AsyncBaseTransport | None = None) -> dict[str, Any]:
    """Asks Overpass once for the streets round `points` (the runs' routes) and keeps them."""
    box = box_round(points)
    if box is None:
        raise ValueError("No routes yet: the streets are fetched round your runs.")
    headers = {"User-Agent": "home-hub (personal, one request)"}
    async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS, transport=transport,
                                 headers=headers) as client:
        resp = await client.post(URL, data={"data": query(box)})
        resp.raise_for_status()
    found = shapes(resp.json())
    ensure_table(store)
    with store.connect() as conn:
        conn.execute("INSERT OR REPLACE INTO street_map (id, fetched_at, box, shapes) "
                     "VALUES (1, ?, ?, ?)",
                     ((now or datetime.now(UTC)).isoformat(), json.dumps(box), json.dumps(found)))
    return status(store)
