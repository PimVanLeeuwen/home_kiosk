"""What needs attention in the media stack: downloads, missing episodes, what airs next.

The hub's Media page and the House panel's Media card. Read-only, every minute,
from Sonarr and Radarr on the NAS with the keys the service tiles already use
(`widgets.host`, `widgets.keys`, the ports from the service catalog):
Sonarr's and Radarr's download queues, Sonarr's wanted list (aired, monitored,
not downloaded) and Sonarr's calendar for the coming week. One app failing
leaves the other's part; posters are served through the hub (see main.py).
"""

from __future__ import annotations

import asyncio
import logging
import re
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

import httpx
from pydantic import BaseModel

from ..models import Envelope
from ..store import Store
from .widgets import describe

log = logging.getLogger(__name__)

CACHE_KEY = "media"
SOURCES = ("sonarr", "radarr")
MISSING_SHOWN = 10
UPCOMING_DAYS = 7
TIMEOUT_SECONDS = 8

State = Literal["downloading", "queued", "paused", "importing", "warning", "failed"]


class MediaDownload(BaseModel):
    id: str  # "sonarr:123", the queue item
    kind: Literal["tv", "movie"]
    title: str  # the series or the movie
    detail: str  # "S2 E5 · The Breakwater" or "Movie · 2025"
    size_bytes: int
    left_bytes: int
    progress_pct: float
    time_left_seconds: int | None
    client: str
    state: State
    message: str | None = None  # Sonarr's or Radarr's own reason for a warning or failure
    poster: str | None = None  # "sonarr/12": /api/media/posters/sonarr/12


class MediaEpisode(BaseModel):
    series: str
    season: int
    episode: int
    title: str
    air_date: datetime | None
    poster: str | None = None


class Media(Envelope):
    downloads: list[MediaDownload]
    missing: list[MediaEpisode]  # newest first, at most MISSING_SHOWN
    missing_total: int
    upcoming: list[MediaEpisode]  # the coming week, soonest first
    errors: dict[str, str] = {}  # source -> a short reason, when it could not be read
    # poster key -> the app's small poster path; what the poster route may fetch
    posters: dict[str, str] = {}


def settings(cfg: dict[str, Any], store: Store) -> dict[str, Any]:
    widgets = cfg.get("widgets") or {}
    keys = widgets.get("keys") or {}
    ports = {s.widget: s.port for s in store.list_services() if s.widget in SOURCES and s.port}
    apps = {name: {"url": f"http://{widgets.get('host', 'localhost')}:{ports[name]}",
                   "key": (keys.get(name) or "").strip()}
            for name in SOURCES if name in ports and (keys.get(name) or "").strip()}
    return {"enabled": bool(apps), "apps": apps}


def _when(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


_TIMELEFT = re.compile(r"^(?:(\d+)\.)?(\d+):(\d+):(\d+)")


def time_left(value: str | None) -> int | None:
    """Sonarr's "01:02:03" or "1.02:03:04" (days.hours) as seconds."""
    match = _TIMELEFT.match(value or "")
    if not match:
        return None
    days, hours, minutes, seconds = (int(part or 0) for part in match.groups())
    return ((days * 24 + hours) * 60 + minutes) * 60 + seconds


def small_poster(owner: Any) -> str | None:
    """The app's own 250-pixel poster of a series or movie, through its API so
    the API key counts (the /MediaCover/ files ask for a login from outside the
    app's local network). The answers' `images[].url` are no help: outside the
    series endpoint they are the remote originals, or left out. A series without
    a poster is a 404 there and a letters tile in the hub."""
    return f"/api/v3/mediacover/{owner}/poster-250.jpg" if owner is not None else None


def _state(item: dict[str, Any]) -> State:
    tracked = item.get("trackedDownloadState") or ""
    if (tracked in ("failed", "failedPending") or item.get("status") == "failed"
            or item.get("trackedDownloadStatus") == "error"):
        return "failed"
    if item.get("trackedDownloadStatus") == "warning" or item.get("status") == "warning":
        return "warning"
    if tracked in ("importPending", "importing"):
        return "importing"
    if item.get("status") == "paused":
        return "paused"
    if item.get("status") in ("queued", "delay"):
        return "queued"
    return "downloading"


def _message(item: dict[str, Any]) -> str | None:
    if item.get("errorMessage"):
        return str(item["errorMessage"])
    for status in item.get("statusMessages") or []:
        messages = status.get("messages") or []
        if messages or status.get("title"):
            return str(messages[0] if messages else status["title"])
    return None


def parse_queue(source: str, body: dict[str, Any],
                posters: dict[str, str]) -> list[MediaDownload]:
    """One app's queue. Adds each item's poster to `posters`."""
    found = []
    for item in body.get("records") or []:
        state = _state(item)
        size = int(item.get("size") or 0)
        left = int(item.get("sizeleft") or 0)
        if source == "sonarr":
            parent, owner = item.get("series") or {}, item.get("seriesId")
            ep = item.get("episode") or {}
            detail = (f"S{ep.get('seasonNumber', 0)} E{ep.get('episodeNumber', 0)}"
                      + (f" · {ep['title']}" if ep.get("title") else ""))
            kind: Literal["tv", "movie"] = "tv"
        else:
            parent, owner = item.get("movie") or {}, item.get("movieId")
            detail = "Movie" + (f" · {parent['year']}" if parent.get("year") else "")
            kind = "movie"
        poster = None
        path = small_poster(owner)
        if path:
            poster = f"{source}/{owner}"
            posters[poster] = path
        found.append(MediaDownload(
            id=f"{source}:{item.get('id')}",
            kind=kind,
            title=parent.get("title") or item.get("title") or "",
            detail=detail,
            size_bytes=size,
            left_bytes=left,
            progress_pct=round((size - left) / size * 100, 1) if size else 0.0,
            time_left_seconds=(None if state in ("failed", "warning")
                               else time_left(item.get("timeleft"))),
            client=item.get("downloadClient") or "",
            state=state,
            message=_message(item) if state in ("failed", "warning") else None,
            poster=poster,
        ))
    return found


def parse_episodes(records: list[dict[str, Any]], posters: dict[str, str]) -> list[MediaEpisode]:
    episodes = []
    for record in records:
        series = record.get("series") or {}
        poster = None
        path = small_poster(record.get("seriesId"))
        if path:
            poster = f"sonarr/{record['seriesId']}"
            posters[poster] = path
        episodes.append(MediaEpisode(
            series=series.get("title") or "",
            season=int(record.get("seasonNumber") or 0),
            episode=int(record.get("episodeNumber") or 0),
            title=record.get("title") or "",
            air_date=_when(record.get("airDateUtc")),
            poster=poster,
        ))
    return episodes


async def _get(client: httpx.AsyncClient, app: dict[str, str], path: str, **params: Any) -> Any:
    resp = await client.get(f"{app['url']}{path}", params=params,
                            headers={"X-Api-Key": app["key"]})
    resp.raise_for_status()
    return resp.json()


async def collect(cfg: dict[str, Any], store: Store, now: datetime | None = None,
                  transport: httpx.AsyncBaseTransport | None = None) -> Media:
    """Raises only when neither Sonarr nor Radarr answers, so the last good
    answer stays cached, flagged stale."""
    apps = settings(cfg, store)["apps"]
    now = now or datetime.now(UTC)
    posters: dict[str, str] = {}
    downloads: list[MediaDownload] = []
    missing: list[MediaEpisode] = []
    upcoming: list[MediaEpisode] = []
    missing_total = 0
    errors: dict[str, str] = {}

    async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS, transport=transport) as client:
        async def sonarr(app: dict[str, str]) -> None:
            nonlocal missing_total
            queue, wanted, calendar = await asyncio.gather(
                _get(client, app, "/api/v3/queue", page=1, pageSize=50,
                     includeSeries="true", includeEpisode="true"),
                _get(client, app, "/api/v3/wanted/missing", page=1, pageSize=MISSING_SHOWN,
                     includeSeries="true", monitored="true",
                     sortKey="airDateUtc", sortDirection="descending"),
                _get(client, app, "/api/v3/calendar", includeSeries="true",
                     start=now.isoformat(), end=(now + timedelta(days=UPCOMING_DAYS)).isoformat()),
            )
            downloads.extend(parse_queue("sonarr", queue, posters))
            missing_total = int(wanted.get("totalRecords") or 0)
            missing.extend(parse_episodes(wanted.get("records") or [], posters))
            upcoming.extend(parse_episodes(calendar if isinstance(calendar, list) else [], posters))

        async def radarr(app: dict[str, str]) -> None:
            queue = await _get(client, app, "/api/v3/queue", page=1, pageSize=50,
                               includeMovie="true")
            downloads.extend(parse_queue("radarr", queue, posters))

        jobs = {"sonarr": sonarr, "radarr": radarr}
        for name, result in zip(apps, await asyncio.gather(
                *(jobs[name](app) for name, app in apps.items()), return_exceptions=True),
                strict=True):
            if isinstance(result, Exception):
                # The class only: an httpx error carries the request, and the request the key.
                log.warning("media: %s failed: %s", name, type(result).__name__)
                errors[name] = describe(result)

    if apps and len(errors) == len(apps):
        raise RuntimeError("neither Sonarr nor Radarr answered")
    order = {"failed": 0, "warning": 1, "downloading": 2, "importing": 3, "paused": 4, "queued": 5}
    downloads.sort(key=lambda d: (order[d.state], -d.progress_pct))
    far = datetime.max.replace(tzinfo=UTC)
    missing.sort(key=lambda e: e.air_date or far, reverse=True)
    upcoming.sort(key=lambda e: e.air_date or far)
    return Media(as_of=now, stale=False, downloads=downloads, missing=missing[:MISSING_SHOWN],
                 missing_total=missing_total, upcoming=upcoming, errors=errors, posters=posters)


# Posters by key and path, so a changed poster (new path) is fetched again.
_posters: dict[tuple[str, str], tuple[bytes, str]] = {}
POSTERS_KEPT = 300


async def poster(cfg: dict[str, Any], store: Store, source: str, item_id: int,
                 transport: httpx.AsyncBaseTransport | None = None) -> tuple[bytes, str]:
    """A poster from the current answer only, so this is not an open proxy.
    Raises LookupError for anything else."""
    key = f"{source}/{item_id}"
    path = ((store.get_cache(CACHE_KEY) or {}).get("posters") or {}).get(key)
    app = settings(cfg, store)["apps"].get(source)
    if not path or not app:
        raise LookupError(key)
    if (key, path) in _posters:
        return _posters[(key, path)]
    async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS, transport=transport) as client:
        resp = await client.get(f"{app['url']}{path}", headers={"X-Api-Key": app["key"]})
        resp.raise_for_status()
    kind = resp.headers.get("content-type", "image/jpeg").split(";")[0]
    if not kind.startswith("image/"):
        raise LookupError(key)
    if len(_posters) >= POSTERS_KEPT:
        _posters.pop(next(iter(_posters)))
    _posters[(key, path)] = (resp.content, kind)
    return resp.content, kind
