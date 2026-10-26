"""The town's streets under the runs (plan.md M28, step 5): fetched from the public Overpass API
(OpenStreetMap) when asked in Settings, one area at a time, then drawn from the hub's own copy.

Runs are grouped into areas (runs within AREA_KM of each other); home is the area with the most
runs. Decided 2026-10-26: the owner fetches home's streets, and those of any other area only if
asked for that area; each request tells Overpass's servers that area, nothing else is sent.

Kept: only the shapes, in three kinds (roads by size, water, parks), positions rounded to about a
metre; no names or other tags.
"""

from __future__ import annotations

import json
import math
from datetime import UTC, datetime
from typing import Any

import httpx

from ..store import Store
from . import runs

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
CREATE TABLE IF NOT EXISTS street_area (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fetched_at TEXT NOT NULL,
    box TEXT NOT NULL,
    shapes TEXT NOT NULL,
    counts TEXT
)
"""
AREA_KM = 15.0  # runs closer than this to an area's middle belong to it
EVER = "1970-01-01T00:00:00+00:00"


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
        # How many of each kind, beside the shapes: a city's shapes take about a second to read,
        # and every panel request asks only whether (and when) an area's streets are in.
        have = {r["name"] for r in conn.execute("PRAGMA table_info(street_area)").fetchall()}
        if "counts" not in have:
            conn.execute("ALTER TABLE street_area ADD COLUMN counts TEXT")
        # Before areas (2026-10-26) one box held every run: kept as home's, or whichever area
        # it covers, until fetched again.
        old = conn.execute("SELECT name FROM sqlite_master WHERE name = 'street_map'").fetchone()
        if old:
            conn.execute("INSERT INTO street_area (fetched_at, box, shapes) "
                         "SELECT fetched_at, box, shapes FROM street_map")
            conn.execute("DROP TABLE street_map")
        for row in conn.execute("SELECT id, shapes FROM street_area "
                                "WHERE counts IS NULL").fetchall():
            conn.execute("UPDATE street_area SET counts = ? WHERE id = ?",
                         (json.dumps(_counts(json.loads(row["shapes"]))), row["id"]))


def _km(a: list[float], b: list[float]) -> float:
    """Roughly, in kilometres: plenty for telling towns apart."""
    dy = (a[0] - b[0]) * 111.2
    dx = (a[1] - b[1]) * 111.2 * math.cos(math.radians((a[0] + b[0]) / 2))
    return math.hypot(dx, dy)


def middle(route: list[list[float]]) -> list[float]:
    return [sum(p[0] for p in route) / len(route), sum(p[1] for p in route) / len(route)]


def group(places: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Runs grouped by area (app/sources/runs.py, `places`), the area with the most runs first:
    {middle, runs (ids), corners (of each run's bounds), last (start)}. A run joins the first
    area whose middle is within AREA_KM of its own."""
    areas: list[dict[str, Any]] = []
    for run in places:
        here = run["middle"]
        area = next((a for a in areas if _km(a["middle"], here) <= AREA_KM), None)
        if area is None:
            area = {"middle": here, "runs": [], "corners": [], "last": run["start"]}
            areas.append(area)
        n = len(area["runs"])
        area["middle"] = [(area["middle"][i] * n + here[i]) / (n + 1) for i in (0, 1)]
        area["runs"].append(run["id"])
        s, w, n_, e = run["box"]
        area["corners"] += [[s, w], [n_, e]]
        area["last"] = max(area["last"], run["start"])
    return sorted(areas, key=lambda a: -len(a["runs"]))


def _inside(box: list[float], point: list[float]) -> bool:
    s, w, n, e = box
    return s <= point[0] <= n and w <= point[1] <= e


def _counts(found: dict[str, list]) -> dict[str, int]:
    return {kind: len(lines) for kind, lines in found.items()}


def _rows(store: Store) -> list[dict[str, Any]]:
    """The areas fetched, without their shapes: {id, fetched_at, box, counts}."""
    ensure_table(store)
    with store.connect() as conn:
        rows = conn.execute("SELECT id, fetched_at, box, counts FROM street_area "
                            "ORDER BY id").fetchall()
    return [{"id": r["id"], "fetched_at": r["fetched_at"], "box": json.loads(r["box"]),
             "counts": json.loads(r["counts"])} for r in rows]


def fetched_for(store: Store, point: list[float]) -> dict[str, Any] | None:
    """Whether (and when) the streets round `point` were fetched, without reading them:
    {id, fetched_at, box, counts}, or None. Cheap enough for every request."""
    return next((r for r in _rows(store) if _inside(r["box"], point)), None)


def shapes_of(store: Store, area_id: int) -> dict[str, list]:
    """An area's shapes: slow for a city (about a second), so only for painting."""
    with store.connect() as conn:
        row = conn.execute("SELECT shapes FROM street_area WHERE id = ?", (area_id,)).fetchone()
    return json.loads(row["shapes"]) if row else {}


def kept_for(store: Store, point: list[float]) -> dict[str, Any] | None:
    """The streets fetched for the area round `point`, with their shapes, or None: for
    painting only (see `fetched_for`)."""
    row = fetched_for(store, point)
    return row | {"shapes": shapes_of(store, row["id"])} if row else None


def at_home(store: Store, since: str) -> dict[str, Any]:
    """The runs from `since` on in the home area (where most runs are, over all time), without
    reading a route: {runs: [{id, start, middle, box}], elsewhere (how many ran elsewhere),
    streets (whether home's are fetched, `fetched_for`)}."""
    areas = group(runs.places(store, EVER))
    home = set(areas[0]["runs"]) if areas else set()
    year = runs.places(store, since)
    mine = [p for p in year if p["id"] in home]
    return {"runs": mine, "elsewhere": len(year) - len(mine),
            "streets": fetched_for(store, areas[0]["middle"]) if areas else None}


def direction(home: list[float], there: list[float]) -> str:
    """"about 80 km north-east": how far and which way an area lies from home."""
    dy = there[0] - home[0]
    dx = (there[1] - home[1]) * math.cos(math.radians(home[0]))
    names = ["east", "north-east", "north", "north-west", "west", "south-west", "south",
             "south-east"]
    way = names[round(math.degrees(math.atan2(dy, dx)) / 45) % 8]
    return f"about {round(_km(home, there) / 5) * 5 or 5} km {way}"


def status(store: Store) -> dict[str, Any]:
    """The areas run in, home first, each with its runs and whether its streets are in."""
    areas = group(runs.places(store, EVER))
    rows = _rows(store)
    out = []
    for i, area in enumerate(areas):
        row = next((r for r in rows if _inside(r["box"], area["middle"])), None)
        counts = row["counts"] if row else {}
        out.append({"key": f"{area['middle'][0]:.3f},{area['middle'][1]:.3f}", "home": i == 0,
                    "runs": len(area["runs"]), "last": area["last"],
                    "where": "home" if i == 0 else direction(areas[0]["middle"], area["middle"]),
                    "fetched_at": row["fetched_at"] if row else None, "counts": counts})
    return {"areas": out}


async def fetch(store: Store, key: str,
                now: datetime | None = None,
                transport: httpx.AsyncBaseTransport | None = None) -> dict[str, Any]:
    """Asks Overpass once for the streets of the area `key` names (its middle, "52.500,3.500")
    and keeps them in place of any fetched for it before."""
    areas = group(runs.places(store, EVER))
    try:
        lat, lon = (float(v) for v in key.split(","))
    except ValueError:
        raise LookupError("No such area.") from None
    area = next((a for a in areas if _km(a["middle"], [lat, lon]) <= 1.0), None)
    if area is None:
        raise LookupError("No such area.")
    box = box_round(area["corners"])
    headers = {"User-Agent": "home-hub (personal, one request)"}
    async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS, transport=transport,
                                 headers=headers) as client:
        resp = await client.post(URL, data={"data": query(box)})
        resp.raise_for_status()
    found = shapes(resp.json())
    ensure_table(store)
    with store.connect() as conn:
        for row in _rows(store):
            if _inside(row["box"], area["middle"]):
                conn.execute("DELETE FROM street_area WHERE id = ?", (row["id"],))
        conn.execute("INSERT INTO street_area (fetched_at, box, shapes, counts) "
                     "VALUES (?, ?, ?, ?)", ((now or datetime.now(UTC)).isoformat(),
                                             json.dumps(box), json.dumps(found),
                                             json.dumps(_counts(found))))
    return status(store)
