from __future__ import annotations

import asyncio
from datetime import UTC, datetime

import httpx
import pytest
from fastapi.testclient import TestClient

from app import main
from app.models import Service
from app.sources import media_status

NOW = datetime(2026, 10, 14, 8, 0, tzinfo=UTC)
CFG = {"widgets": {"host": "nas", "keys": {"sonarr": "s-key", "radarr": "r-key"}}}


def images(item_id: int) -> list[dict]:
    return [{"coverType": "fanart", "url": f"/MediaCover/{item_id}/fanart.jpg?lastWrite=1"},
            {"coverType": "poster", "url": f"/MediaCover/{item_id}/poster.jpg?lastWrite=1"}]


SERIES = {"title": "Harbour Lights", "year": 2024, "images": images(12)}
QUEUE_TV = {"totalRecords": 3, "records": [
    {"id": 1, "seriesId": 12, "series": SERIES,
     "episode": {"seasonNumber": 2, "episodeNumber": 5, "title": "The Breakwater"},
     "size": 1_400_000_000, "sizeleft": 392_000_000, "timeleft": "00:06:12",
     "status": "downloading", "trackedDownloadStatus": "ok", "trackedDownloadState": "downloading",
     "downloadClient": "SABnzbd"},
    {"id": 2, "seriesId": 30, "series": {"title": "Northbound", "images": images(30)},
     "episode": {"seasonNumber": 3, "episodeNumber": 2, "title": "Cold Front"},
     "size": 2_100_000_000, "sizeleft": 1_239_000_000, "timeleft": "1.02:00:00",
     "status": "warning", "trackedDownloadStatus": "warning", "trackedDownloadState": "downloading",
     "statusMessages": [{"title": "Cold Front",
                         "messages": ["The download is stalled with no connections"]}],
     "downloadClient": "Transmission"},
    {"id": 3, "seriesId": 12, "series": SERIES,
     "episode": {"seasonNumber": 2, "episodeNumber": 4, "title": "Slack Tide"},
     "size": 1_300_000_000, "sizeleft": 0, "timeleft": None,
     "status": "completed", "trackedDownloadStatus": "error",
     "trackedDownloadState": "importPending",
     "errorMessage": "Not enough free space", "downloadClient": "SABnzbd"},
]}
QUEUE_MOVIES = {"totalRecords": 1, "records": [
    {"id": 7, "movieId": 5, "movie": {"title": "Glass Harbour", "year": 2025, "images": images(5)},
     "size": 8_200_000_000, "sizeleft": 5_658_000_000, "timeleft": "00:24:00",
     "status": "downloading", "trackedDownloadStatus": "ok", "trackedDownloadState": "downloading",
     "downloadClient": "SABnzbd"}]}
WANTED = {"totalRecords": 14, "records": [
    {"seriesId": 30, "seasonNumber": 3, "episodeNumber": 1, "title": "Thaw",
     "airDateUtc": "2026-10-07T21:00:00Z", "series": {"title": "Northbound", "images": images(30)}},
    {"seriesId": 44, "seasonNumber": 1, "episodeNumber": 5, "title": "Low Water",
     "airDateUtc": "2026-10-13T20:00:00Z", "series": {"title": "The Long Coast", "images": []}},
]}
CALENDAR = [
    {"seriesId": 12, "seasonNumber": 2, "episodeNumber": 6, "title": "Spring Tide",
     "airDateUtc": "2026-10-16T01:00:00Z", "series": SERIES},
    {"seriesId": 44, "seasonNumber": 1, "episodeNumber": 6, "title": "High Water",
     "airDateUtc": "2026-10-14T19:00:00Z", "series": {"title": "The Long Coast", "images": []}},
]


class Apps:
    """Fake Sonarr (8989) and Radarr (7878) on the host `nas`."""

    def __init__(self, down: tuple[str, ...] = ()):
        self.down, self.seen = down, []

    def transport(self) -> httpx.MockTransport:
        def handler(request: httpx.Request) -> httpx.Response:
            app = {8989: "sonarr", 7878: "radarr"}[request.url.port]
            self.seen.append((app, request.url.path, request.headers.get("X-Api-Key")))
            if app in self.down:
                return httpx.Response(503)
            if request.url.path.startswith("/MediaCover/"):
                return httpx.Response(200, content=b"jpeg", headers={"content-type": "image/jpeg"})
            answer = {("sonarr", "/api/v3/queue"): QUEUE_TV,
                      ("radarr", "/api/v3/queue"): QUEUE_MOVIES,
                      ("sonarr", "/api/v3/wanted/missing"): WANTED,
                      ("sonarr", "/api/v3/calendar"): CALENDAR}[(app, request.url.path)]
            return httpx.Response(200, json=answer)

        return httpx.MockTransport(handler)


@pytest.fixture
def media_store(store):
    store.seed_services([
        Service(id="sonarr", name="Sonarr", group="Downloads", port=8989, container="sonarr",
                widget="sonarr"),
        Service(id="radarr", name="Radarr", group="Downloads", port=7878, container="radarr",
                widget="radarr"),
    ])
    return store


def collect(store, apps: Apps) -> media_status.Media:
    return asyncio.run(media_status.collect(CFG, store, now=NOW, transport=apps.transport()))


def test_time_left_and_small_posters():
    assert media_status.time_left("00:06:12") == 372
    assert media_status.time_left("1.02:00:00") == 26 * 3600
    assert media_status.time_left(None) is None
    assert media_status.small_poster(images(12)) == "/MediaCover/12/poster-250.jpg"
    assert media_status.small_poster([]) is None


def test_downloads_with_progress_states_and_reasons(media_store):
    apps = Apps()
    media = collect(media_store, apps)

    shown = [(d.title, d.detail, d.state, d.progress_pct, d.time_left_seconds, d.message)
             for d in media.downloads]
    assert shown == [
        ("Harbour Lights", "S2 E4 · Slack Tide", "failed", 100.0, None, "Not enough free space"),
        ("Northbound", "S3 E2 · Cold Front", "warning", 41.0, None,
         "The download is stalled with no connections"),
        ("Harbour Lights", "S2 E5 · The Breakwater", "downloading", 72.0, 372, None),
        ("Glass Harbour", "Movie · 2025", "downloading", 31.0, 1440, None),
    ]
    assert media.downloads[3].kind == "movie" and media.downloads[3].client == "SABnzbd"
    # Each app gets its own key.
    assert {(app, key) for app, _, key in apps.seen} == {("sonarr", "s-key"), ("radarr", "r-key")}


def test_missing_newest_first_with_the_total_and_the_week_ahead(media_store):
    media = collect(media_store, Apps())

    assert media.missing_total == 14
    assert [(e.series, e.season, e.episode) for e in media.missing] == [
        ("The Long Coast", 1, 5), ("Northbound", 3, 1)]
    assert [(e.series, e.title) for e in media.upcoming] == [
        ("The Long Coast", "High Water"), ("Harbour Lights", "Spring Tide")]


def test_posters_are_listed_by_key_only_for_items_that_have_one(media_store):
    media = collect(media_store, Apps())

    assert media.downloads[0].poster == "sonarr/12"
    assert media.downloads[3].poster == "radarr/5"
    assert media.missing[0].poster is None  # The Long Coast has no poster yet
    assert media.posters == {"sonarr/12": "/MediaCover/12/poster-250.jpg",
                             "sonarr/30": "/MediaCover/30/poster-250.jpg",
                             "radarr/5": "/MediaCover/5/poster-250.jpg"}


def test_one_app_down_leaves_the_other(media_store):
    media = collect(media_store, Apps(down=("radarr",)))

    assert media.errors == {"radarr": "HTTP 503"}
    assert {d.kind for d in media.downloads} == {"tv"}
    assert media.missing_total == 14


def test_both_down_raises_so_the_last_answer_goes_stale(media_store):
    with pytest.raises(RuntimeError):
        collect(media_store, Apps(down=("sonarr", "radarr")))


def test_off_without_keys(media_store):
    assert media_status.settings({"widgets": {"keys": {}}}, media_store)["enabled"] is False
    assert media_status.settings(CFG, media_store)["apps"]["radarr"] == {
        "url": "http://nas:7878", "key": "r-key"}


def test_posters_only_for_the_current_answer(media_store):
    answer = collect(media_store, Apps()).model_dump(mode="json")
    media_store.put_cache(media_status.CACHE_KEY, answer)
    apps = Apps()

    data, kind = asyncio.run(media_status.poster(CFG, media_store, "sonarr", 12,
                                                 transport=apps.transport()))

    assert (data, kind) == (b"jpeg", "image/jpeg")
    assert apps.seen == [("sonarr", "/MediaCover/12/poster-250.jpg", "s-key")]
    with pytest.raises(LookupError):
        asyncio.run(media_status.poster(CFG, media_store, "sonarr", 99, transport=apps.transport()))
    with pytest.raises(LookupError):
        asyncio.run(media_status.poster(CFG, media_store, "jellyfin", 12,
                                        transport=apps.transport()))


def test_the_routes_serve_the_answer_and_refuse_unknown_posters(media_store):
    # No `with`: the lifespan would start the scheduler and hit real sources.
    main.app.state.store = media_store
    main.app.state.config = CFG
    client = TestClient(main.app)
    assert client.get("/api/media").status_code == 503  # nothing collected yet

    answer = collect(media_store, Apps()).model_dump(mode="json")
    media_store.put_cache(media_status.CACHE_KEY, answer)

    assert client.get("/api/media").json()["missing_total"] == 14
    assert client.get("/api/media/posters/sonarr/99").status_code == 404
