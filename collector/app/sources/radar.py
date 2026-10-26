"""The rain radar (plan.md M27, I): Buienradar's radar pictures of the Netherlands, read
only while rain is expected within two hours (the weather's rain line), every 5 minutes.
Public pictures, no key; nothing is sent but the request.

Kept in memory: the latest rain layer (see-through), with the frame's time from Buienradar's
own file name. The Now panel's radar piece is painted from it over the hub's own outline of
the land (app/paint_radar.py); Buienradar's map is not fetched, as its rain is drawn in.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any

import httpx

from ..models import Envelope
from ..store import Store
from . import weather

CACHE_KEY = "radar"
URL = "https://image.buienradar.nl/2.0/image/single/RadarMapRainNL"
SIZE = (500, 512)
WET_MM = 0.1
TIMEOUT_SECONDS = 20
STAMP = re.compile(r"/(\d{12})__")  # 202610260705: the frame's time, UTC

# Where a place falls on Buienradar's 500 x 512 picture (fitted to Den Helder, Vlissingen
# and Groningen; good to a few pixels over the Netherlands).
X0, PX_PER_LON = 19.0, 47.9
LAT0, Y0, PX_PER_LAT = 52.96, 160.0, 100.0


def to_pixel(lat: float, lon: float) -> tuple[float, float]:
    return X0 + lon * PX_PER_LON, Y0 + (LAT0 - lat) * PX_PER_LAT


class Radar(Envelope):
    stamp: str | None  # the rain layer's frame, "202610260705"
    wet: bool          # rain expected within two hours
    home: list[float] = []  # where home falls on Buienradar's picture


class Frames:
    def __init__(self) -> None:
        self.rain: bytes | None = None
        self.stamp: str | None = None


FRAMES = Frames()


def wet(store: Store) -> bool:
    points = (store.get_cache(weather.CACHE_KEY) or {}).get("rain") or []
    return any((p.get("mm_per_hour") or 0) >= WET_MM for p in points)


async def _fetch(client: httpx.AsyncClient) -> tuple[str | None, bytes]:
    params = {"height": SIZE[1], "width": SIZE[0], "renderBackground": "False",
              "renderBranding": "False", "renderText": "False"}
    resp = await client.get(URL, params=params)
    resp.raise_for_status()
    found = STAMP.search(str(resp.url))
    return (found.group(1) if found else None), resp.content


async def collect(cfg: dict[str, Any], store: Store, now: datetime | None = None,
                  transport: httpx.AsyncBaseTransport | None = None) -> Radar:
    now = now or datetime.now(UTC)
    w = weather.settings(cfg)
    home = [round(v, 1) for v in to_pixel(w["lat"], w["lon"])]
    if not wet(store):
        return Radar(as_of=now, stale=False, stamp=FRAMES.stamp, wet=False, home=home)
    async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS, follow_redirects=True,
                                 transport=transport) as client:
        stamp, rain = await _fetch(client)
    FRAMES.rain, FRAMES.stamp = rain, stamp
    return Radar(as_of=now, stale=False, stamp=stamp, wet=True, home=home)
