"""The House panel's Media screen (plan.md M20, refocused 2026-10-12): not what is being
watched but what needs attention: what is downloading, with its poster, progress and
time left, and the missing episodes (aired, not downloaded); then the next episode to
air. With nothing downloading or missing it says Up to date and shows the week ahead.
Ready to draw, from `/api/media` (sources/media_status.py); posters come to the panel
as small baseline JPEGs (decided 2026-10-22), made from the ones the hub fetches.
"""

from __future__ import annotations

import asyncio
import io
from collections import OrderedDict
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from PIL import Image, ImageOps

from .panel_text import latin1
from .sources import media_status
from .store import Store

MAX_DOWNLOADS = 2
MAX_MISSING = 2
MAX_UPCOMING = 3
POSTER = (96, 144)  # multiples of 16, for the panel's decoder
STATE_WORDS = {"queued": "Queued", "paused": "Paused", "importing": "Importing",
               "warning": "Needs a look", "failed": "Failed"}
_posters: OrderedDict[str, bytes] = OrderedDict()
KEEP_POSTERS = 16


def _left(seconds: int | None) -> str:
    """"6 min", "1 h 20 min", "" when nobody knows."""
    if seconds is None:
        return ""
    minutes = max(1, round(seconds / 60))
    hours, minutes = divmod(minutes, 60)
    return f"{hours} h {minutes} min" if hours else f"{minutes} min"


def _day(at: str | None, zone: ZoneInfo, now: datetime) -> str:
    """"today", "tomorrow", "Friday", "3 Nov"."""
    if not at:
        return ""
    day = datetime.fromisoformat(at).astimezone(zone).date()
    days = (day - now.astimezone(zone).date()).days
    if days == 0:
        return "today"
    if days == 1:
        return "tomorrow"
    if 1 < days < 7:
        return day.strftime("%A")
    return f"{day.day} {day.strftime('%b')}"


def _aired(at: str | None, zone: ZoneInfo, now: datetime) -> str:
    """"aired today", "aired yesterday", "aired 3 days ago"."""
    if not at:
        return "aired"
    days = (now.astimezone(zone).date() - datetime.fromisoformat(at).astimezone(zone).date()).days
    if days <= 0:
        return "aired today"
    return "aired yesterday" if days == 1 else f"aired {days} days ago"


def _episode(e: dict[str, Any]) -> str:
    return f"S{e['season']} E{e['episode']}"


def _poster_path(key: str | None) -> str | None:
    return f"/api/desk/poster/{key}" if key else None


def media_screen(store: Store, zone: ZoneInfo, now: datetime) -> dict[str, Any]:
    data = store.get_cache(media_status.CACHE_KEY)
    if not data:
        return {"kind": "media", "stale": False, "present": False}
    downloads = data.get("downloads") or []
    missing = data.get("missing") or []
    total = data.get("missing_total") or len(missing)
    upcoming = data.get("upcoming") or []
    failing = [d for d in downloads if d["state"] in ("failed", "warning")]
    active = [d for d in downloads if d["state"] not in ("failed", "warning")]
    if failing:
        status, tone = f"{len(failing)} NEED{'S' if len(failing) == 1 else ''} A LOOK", "warn"
    elif active:
        status, tone = f"{len(active)} DOWNLOADING", "busy"
    elif total:
        status, tone = f"{total} MISSING", "warn"
    else:
        status, tone = "UP TO DATE", "ok"
    return {
        "kind": "media",
        "stale": bool(data.get("stale")),
        "present": True,
        "title": "MEDIA",
        "status": status,
        "tone": tone,
        "downloads": [{
            "title": latin1(d["title"]), "detail": latin1(d.get("detail") or ""),
            "progress": round(min(100.0, max(0.0, d.get("progress_pct") or 0)) * 10),
            "pct": f"{int(d.get('progress_pct') or 0)}%",
            "left": STATE_WORDS.get(d["state"]) or _left(d.get("time_left_seconds")),
            "state": d["state"],
            "poster": _poster_path(d.get("poster")),
        } for d in downloads[:MAX_DOWNLOADS]],
        "missing_title": f"MISSING · {total} EPISODE{'S' if total != 1 else ''}" if total else "",
        "missing": [{"title": latin1(e["series"]), "episode": _episode(e),
                     "line": _aired(e.get("air_date"), zone, now)} for e in missing[:MAX_MISSING]],
        "next": (f"Next to air: {latin1(upcoming[0]['series'])} {_episode(upcoming[0])}, "
                 f"{_day(upcoming[0].get('air_date'), zone, now)}".rstrip(", ")
                 if upcoming else ""),
        # With nothing to see to, the week ahead instead.
        "week": [] if downloads or total else [
            {"title": latin1(e["series"]), "episode": _episode(e),
             "line": _day(e.get("air_date"), zone, now)} for e in upcoming[:MAX_UPCOMING]],
    }


async def poster(cfg: dict[str, Any], store: Store, source: str, item_id: int) -> bytes:
    """A download's poster as a small baseline JPEG for the panel; LookupError when it
    is not one of the current answer's posters."""
    key = f"{source}/{item_id}"
    if key in _posters:
        _posters.move_to_end(key)
        return _posters[key]
    found, _ = await media_status.poster(cfg, store, source, item_id)

    def make() -> bytes:
        with Image.open(io.BytesIO(found)) as image:
            fitted = ImageOps.fit(image.convert("RGB"), POSTER, Image.Resampling.LANCZOS)
        out = io.BytesIO()
        fitted.save(out, "JPEG", quality=85, progressive=False, subsampling="4:2:0")
        return out.getvalue()

    _posters[key] = await asyncio.to_thread(make)
    while len(_posters) > KEEP_POSTERS:
        _posters.popitem(last=False)
    return _posters[key]
