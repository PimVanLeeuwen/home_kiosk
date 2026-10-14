"""The Jellyfin overview on the Media page: who watched how much, the library, requests.

From Tracearr's public API (v2, a `trr_pub_` key in .env): each person's plays
and watch time over the last 30 days and their most-watched genres, the
Jellyfin libraries' counts, and what was added this week. From Jellyseerr: how
many requests wait, are being fetched or became available. Read-only, every
five minutes; one source failing leaves the other. Tracearr's people records
also carry email addresses: only ids and usernames are read.
"""

from __future__ import annotations

import asyncio
import logging
from collections import Counter
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

import httpx
from pydantic import BaseModel

from ..models import Envelope
from ..store import Store
from .widgets import describe

log = logging.getLogger(__name__)

CACHE_KEY = "media_overview"
TRACEARR_API = "/api/v2/public"
GENRES_SHOWN = 5
REQUESTS_SHOWN = 8
# Seerr's request status (1 waiting, 2 approved, 3 declined, 4 failed, 5 done)
# and media status (2 pending, 3 processing, 4 partly, 5 available).
REQUEST_STATE = {1: "waiting", 3: "declined", 4: "failed"}
MEDIA_STATE = {3: "downloading", 4: "partly", 5: "available"}
# Titles by "tv/123" or "movie/123": a title does not change, so one lookup each.
_titles: dict[str, tuple[str, str | None]] = {}
WEEK = timedelta(days=7)
# Recently added comes newest first, 50 a page; a busy week rarely needs more.
ADDED_PAGES = 3
TIMEOUT_SECONDS = 10


class Viewer(BaseModel):
    name: str  # the Tracearr username
    plays: int
    watch_seconds: int


class MediaLibrary(BaseModel):
    movies: int
    shows: int
    episodes: int
    size_bytes: int
    added_movies: int  # this week
    added_episodes: int


class RequestCounts(BaseModel):
    pending: int  # waiting for approval
    processing: int  # approved, being fetched
    available: int
    completed: int = 0  # done, all time


class MediaRequest(BaseModel):
    title: str
    year: str | None
    kind: Literal["tv", "movie"]
    by: str  # Seerr's display name of who asked
    # Where it stands, from the request's and the item's status in Seerr.
    state: Literal["waiting", "approved", "downloading", "partly", "available", "declined",
                   "failed"]
    poster: str | None = None  # "sonarr/12", served by /api/media/posters/…


class MediaOverview(Envelope):
    viewers: list[Viewer] | None  # with plays in the last 30 days, most watch time first
    idle_viewers: int = 0  # people without plays in the last 30 days
    genres: list[str] = []  # the household's most-watched, all time
    library: MediaLibrary | None
    requests: RequestCounts | None
    latest_requests: list[MediaRequest] = []
    errors: dict[str, str] = {}  # source -> a short reason


def settings(cfg: dict[str, Any], store: Store) -> dict[str, Any]:
    widgets = cfg.get("widgets") or {}
    keys = widgets.get("keys") or {}
    host = widgets.get("host", "localhost")
    ports = {s.id: s.port for s in store.list_services() if s.port}
    apps = {}
    for name in ("tracearr", "jellyseerr"):
        key = (keys.get(name) or "").strip()
        if key and ports.get(name):
            apps[name] = {"url": f"http://{host}:{ports[name]}", "key": key}
    return {"enabled": "tracearr" in apps, "apps": apps}


def parse_viewers(users: list[dict[str, Any]],
                  stats: dict[str, dict[str, Any]]) -> tuple[list[Viewer], int, list[str]]:
    """The last 30 days per person (only ids and usernames are read from a
    person), how many had no plays, and the household's top genres."""
    viewers, idle, genres = [], 0, Counter()
    for user in users:
        mine = stats.get(user["id"]) or {}
        window = (mine.get("windows") or {}).get("last_30") or {}
        for genre in mine.get("top_genres") or []:
            genres[genre["genre"]] += int(genre.get("plays") or 0)
        plays = int(window.get("plays") or 0)
        if plays == 0:
            idle += 1
            continue
        viewers.append(Viewer(name=user.get("username") or "?", plays=plays,
                              watch_seconds=int(window.get("watch_time_ms") or 0) // 1000))
    viewers.sort(key=lambda v: v.watch_seconds, reverse=True)
    return viewers, idle, [g for g, _ in genres.most_common(GENRES_SHOWN)]


def parse_library(libraries: list[dict[str, Any]], added: list[dict[str, Any]],
                  now: datetime) -> MediaLibrary:
    since = now - WEEK
    recent = Counter(
        item.get("media_type") for item in added
        if not item.get("removed_at") and (_when(item.get("added_at")) or since) > since)
    return MediaLibrary(
        movies=sum(int(x.get("movie_count") or 0) for x in libraries),
        shows=sum(int(x.get("show_count") or 0) for x in libraries),
        episodes=sum(int(x.get("episode_count") or 0) for x in libraries),
        size_bytes=sum(int(x.get("total_file_size") or 0) for x in libraries),
        added_movies=recent["movie"],
        added_episodes=recent["episode"],
    )


def _when(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


async def _get(client: httpx.AsyncClient, url: str, headers: dict[str, str],
               **params: Any) -> Any:
    resp = await client.get(url, params=params, headers=headers)
    resp.raise_for_status()
    return resp.json()


async def _tracearr(client: httpx.AsyncClient, app: dict[str, str],
                    now: datetime) -> tuple[list[Viewer], int, list[str], MediaLibrary]:
    auth = {"Authorization": f"Bearer {app['key']}"}
    base = f"{app['url']}{TRACEARR_API}"
    users = (await _get(client, f"{base}/users", auth, pageSize=100)).get("data") or []
    answers = await asyncio.gather(
        *(_get(client, f"{base}/users/{u['id']}/stats", auth) for u in users))
    stats = {u["id"]: a for u, a in zip(users, answers, strict=True)}
    libraries = (await _get(client, f"{base}/libraries", auth)).get("data") or []
    added: list[dict[str, Any]] = []
    cursor = None
    for _ in range(ADDED_PAGES):
        page = await _get(client, f"{base}/recently-added", auth, pageSize=50,
                          **({"cursor": cursor} if cursor else {}))
        added += page.get("data") or []
        cursor = (page.get("meta") or {}).get("nextCursor")
        oldest = _when(added[-1].get("added_at")) if added else None
        if not cursor or (oldest and oldest < now - WEEK):
            break
    viewers, idle, genres = parse_viewers(users, stats)
    return viewers, idle, genres, parse_library(libraries, added, now)


def request_state(request: dict[str, Any]) -> str:
    if request.get("status") in REQUEST_STATE:
        return REQUEST_STATE[request["status"]]
    return MEDIA_STATE.get((request.get("media") or {}).get("status"), "approved")


async def _title(client: httpx.AsyncClient, app: dict[str, str],
                 media: dict[str, Any]) -> tuple[str, str | None]:
    ref = f"{'movie' if media.get('mediaType') == 'movie' else 'tv'}/{media.get('tmdbId')}"
    if ref not in _titles:
        item = await _get(client, f"{app['url']}/api/v1/{ref}", {"X-Api-Key": app["key"]})
        date = item.get("releaseDate") or item.get("firstAirDate") or ""
        _titles[ref] = (item.get("title") or item.get("name") or "?", date[:4] or None)
    return _titles[ref]


async def _jellyseerr(client: httpx.AsyncClient,
                      app: dict[str, str]) -> tuple[RequestCounts, list[MediaRequest]]:
    """The counts, and the latest requests with their titles. Of who asked, only
    the display name is read (a request also carries the person's email)."""
    auth = {"X-Api-Key": app["key"]}
    counts, listed = await asyncio.gather(
        _get(client, f"{app['url']}/api/v1/request/count", auth),
        _get(client, f"{app['url']}/api/v1/request", auth, take=REQUESTS_SHOWN,
             sort="added", filter="all"))
    results = listed.get("results") or []
    titles = await asyncio.gather(*(_title(client, app, r.get("media") or {}) for r in results))
    latest = []
    for request, (title, year) in zip(results, titles, strict=True):
        media = request.get("media") or {}
        kind: Literal["tv", "movie"] = "movie" if media.get("mediaType") == "movie" else "tv"
        owner = media.get("externalServiceId")
        latest.append(MediaRequest(
            title=title, year=year, kind=kind,
            by=(request.get("requestedBy") or {}).get("displayName") or "?",
            state=request_state(request),
            poster=f"{'radarr' if kind == 'movie' else 'sonarr'}/{owner}" if owner else None))
    return RequestCounts(pending=int(counts.get("pending") or 0),
                         processing=int(counts.get("processing") or 0),
                         available=int(counts.get("available") or 0),
                         completed=int(counts.get("completed") or 0)), latest


async def collect(cfg: dict[str, Any], store: Store, now: datetime | None = None,
                  transport: httpx.AsyncBaseTransport | None = None) -> MediaOverview:
    """Raises only when nothing could be read, so the last good answer stays
    cached, flagged stale."""
    apps = settings(cfg, store)["apps"]
    now = now or datetime.now(UTC)
    overview = MediaOverview(as_of=now, stale=False, viewers=None, library=None, requests=None)
    async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS, transport=transport) as client:
        jobs = {}
        if "tracearr" in apps:
            jobs["tracearr"] = _tracearr(client, apps["tracearr"], now)
        if "jellyseerr" in apps:
            jobs["jellyseerr"] = _jellyseerr(client, apps["jellyseerr"])
        results = await asyncio.gather(*jobs.values(), return_exceptions=True)
    for name, result in zip(jobs, results, strict=True):
        if isinstance(result, Exception):
            # The class only: an httpx error carries the request, and the request the key.
            log.warning("media overview: %s failed: %s", name, type(result).__name__)
            overview.errors[name] = describe(result)
        elif name == "tracearr":
            overview.viewers, overview.idle_viewers, overview.genres, overview.library = result
        else:
            overview.requests, overview.latest_requests = result
    if jobs and len(overview.errors) == len(jobs):
        raise RuntimeError("neither Tracearr nor Jellyseerr answered")
    return overview
