"""The photo of the day (plan.md M27, E): one of Immich's "on this day" memories, chosen on
the NAS with Immich's own help and no AI call: pictures with people you named come first
(Immich's face recognition), then the others; text-like pictures are left out, with
Immich's smart search (its local CLIP) and the camera: a picture without one is a
screenshot. Read each morning, and at start-up.

The key is the Immich one in the NAS-only .env (`IMMICH_API_KEY`); Immich is reached as
the service tiles reach it. People's names and the picture are personal data: served to
the panel, never logged. The picture is kept in memory only.
"""

from __future__ import annotations

import logging
from datetime import UTC, date, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import httpx

from ..models import Envelope
from ..store import Store

log = logging.getLogger(__name__)

CACHE_KEY = "photo"
PORT = 2283  # Immich's, as in the service catalog
TIMEOUT_SECONDS = 30
TEXT_QUERY = "a screenshot, a receipt, a document, a whiteboard or a page of text"
TEXT_SHARE = 1 / 3  # the most text-like third of a day's pictures is left out
MAX_PEOPLE = 3


class Photo(Envelope):
    asset: str | None       # the chosen picture's id in Immich
    taken: str | None       # its date, YYYY-MM-DD
    years: int | None       # how long ago
    people: list[str] = []  # the named people in it, at most MAX_PEOPLE


class Kept:
    def __init__(self) -> None:
        self.asset: str | None = None
        self.picture: bytes | None = None


KEPT = Kept()


def settings(cfg: dict[str, Any]) -> dict[str, Any]:
    widgets = cfg.get("widgets") or {}
    key = ((widgets.get("keys") or {}).get("immich") or "").strip()
    host = widgets.get("host") or "localhost"
    url = ((cfg.get("photo") or {}).get("immich_url") or f"http://{host}:{PORT}").rstrip("/")
    return {"enabled": bool(key), "key": key, "url": url}


def text_like(asset: dict[str, Any], rank: float | None) -> bool:
    """A screenshot (no camera, a PNG) or among the most text-like of its day."""
    exif = asset.get("exifInfo") or {}
    screenshot = not exif.get("make") and (asset.get("originalMimeType") or "").endswith("png")
    return screenshot or (rank is not None and rank < TEXT_SHARE)


def named(asset: dict[str, Any]) -> list[str]:
    return [p["name"] for p in asset.get("people") or [] if (p.get("name") or "").strip()]


def choose(candidates: list[tuple[dict[str, Any], float | None]]) -> dict[str, Any] | None:
    """The best of the day's pictures: named people first, then the least text-like."""
    kept = [(a, r) for a, r in candidates if not text_like(a, r)]
    if not kept:
        return None
    kept.sort(key=lambda ar: (not named(ar[0]), -(ar[1] if ar[1] is not None else 0.5),
                              ar[0]["id"]))
    return kept[0][0]


async def _text_ranks(client: httpx.AsyncClient, s: dict[str, Any], day: date,
                      tz: Any) -> dict[str, float]:
    """Each of a day's pictures by how text-like Immich's smart search finds it: 0 the most,
    towards 1 the least."""
    start = datetime.combine(day, time(0), tz)
    body = {"query": TEXT_QUERY, "type": "IMAGE", "size": 250,
            "takenAfter": start.astimezone(UTC).isoformat(),
            "takenBefore": (start + timedelta(days=1)).astimezone(UTC).isoformat()}
    resp = await client.post(f"{s['url']}/api/search/smart", json=body)
    resp.raise_for_status()
    items = ((resp.json().get("assets") or {}).get("items")) or []
    return {item["id"]: i / max(1, len(items)) for i, item in enumerate(items)}


async def collect(cfg: dict[str, Any], store: Store, now: datetime | None = None,
                  transport: httpx.AsyncBaseTransport | None = None) -> Photo:
    s = settings(cfg)
    tz = ZoneInfo(cfg.get("timezone", "Europe/Amsterdam"))
    now = now or datetime.now(UTC)
    today = now.astimezone(tz).date()
    async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS, transport=transport,
                                 headers={"x-api-key": s["key"]}) as client:
        resp = await client.get(f"{s['url']}/api/memories",
                                params={"for": datetime.combine(today, time(12), tz).isoformat()})
        resp.raise_for_status()
        best: tuple[dict[str, Any], date] | None = None
        for memory in resp.json():
            images = [a for a in memory.get("assets") or [] if a.get("type") == "IMAGE"]
            if not images:
                continue
            taken = _taken(images[0], tz) or today
            ranks = await _text_ranks(client, s, taken, tz) if len(images) > 2 else {}
            pick = choose([(a, ranks.get(a["id"])) for a in images])
            if pick and (best is None or (named(pick) and not named(best[0]))):
                best = (pick, taken)
        if best is None:
            KEPT.asset, KEPT.picture = None, None
            return Photo(as_of=now, stale=False, asset=None, taken=None, years=None)
        asset, taken = best
        if KEPT.asset != asset["id"] or KEPT.picture is None:
            got = await client.get(f"{s['url']}/api/assets/{asset['id']}/thumbnail",
                                   params={"size": "preview"})
            got.raise_for_status()
            KEPT.asset, KEPT.picture = asset["id"], got.content
    return Photo(as_of=now, stale=False, asset=asset["id"], taken=taken.isoformat(),
                 years=today.year - taken.year, people=named(asset)[:MAX_PEOPLE])


def _taken(asset: dict[str, Any], tz: Any) -> date | None:
    when = (asset.get("exifInfo") or {}).get("dateTimeOriginal") or asset.get("fileCreatedAt")
    try:
        return datetime.fromisoformat(when.replace("Z", "+00:00")).astimezone(tz).date()
    except (AttributeError, ValueError):
        return None
