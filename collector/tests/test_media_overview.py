from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from app import main
from app.models import Service
from app.sources import media_overview

TRACEARR = json.loads((Path(__file__).parent / "fixtures" / "tracearr.json").read_text())
SEERR = json.loads((Path(__file__).parent / "fixtures" / "seerr.json").read_text())
CFG = {"widgets": {"host": "nas", "keys": {"tracearr": "trr_pub_test", "jellyseerr": "js-key"}}}
NOW = datetime(2026, 10, 6, 12, 0, tzinfo=UTC)  # a week after the fixture's last additions
COUNTS = SEERR["count"]


@pytest.fixture(autouse=True)
def fresh_titles(monkeypatch):
    monkeypatch.setattr(media_overview, "_titles", {})


@pytest.fixture
def overview_store(store):
    store.seed_services([
        Service(id="tracearr", name="Tracearr", group="Media", port=3000, container="tracearr"),
        Service(id="jellyseerr", name="Jellyseerr", group="Media", port=5055,
                container="jellyseerr", widget="jellyseerr"),
        Service(id="sonarr", name="Sonarr", group="Downloads", port=8989, container="sonarr",
                widget="sonarr"),
    ])
    return store


class Apps:
    def __init__(self, down: tuple[str, ...] = ()):
        self.down, self.seen = down, []

    def transport(self) -> httpx.MockTransport:
        def handler(request: httpx.Request) -> httpx.Response:
            app = {3000: "tracearr", 5055: "jellyseerr"}[request.url.port]
            self.seen.append((app, request.url.path, dict(request.url.params)))
            if app in self.down:
                return httpx.Response(503)
            if app == "jellyseerr":
                assert request.headers["X-Api-Key"] == "js-key"
                path = request.url.path.removeprefix("/api/v1")
                if path == "/request/count":
                    return httpx.Response(200, json=COUNTS)
                if path == "/request":
                    return httpx.Response(200, json=SEERR["requests"])
                if path == "/tv/213375":
                    return httpx.Response(200, json=SEERR["media_213375"])
                kind, tmdb = path.strip("/").split("/")
                name = "title" if kind == "movie" else "name"
                return httpx.Response(200, json={name: f"Item {tmdb}", "releaseDate": "2024-05-01"})
            assert request.headers["Authorization"] == "Bearer trr_pub_test"
            path = request.url.path.removeprefix("/api/v2/public")
            if path == "/users":
                return httpx.Response(200, json=TRACEARR["users"])
            if path.startswith("/users/") and path.endswith("/stats"):
                return httpx.Response(200, json=TRACEARR["stats"][path.split("/")[2]])
            if path == "/libraries":
                return httpx.Response(200, json=TRACEARR["libraries"])
            if path == "/recently-added":
                return httpx.Response(200, json=TRACEARR["recently_added"])
            return httpx.Response(404)

        return httpx.MockTransport(handler)


def collect(store, apps: Apps) -> media_overview.MediaOverview:
    return asyncio.run(media_overview.collect(CFG, store, now=NOW, transport=apps.transport()))


def test_the_leaderboard_has_people_who_watched_in_30_days(overview_store):
    result = collect(overview_store, Apps())

    assert [(v.name, v.plays, v.watch_seconds) for v in result.viewers] == [
        ("alex", 113, 291_274), ("pim", 49, 105_334)]
    assert result.idle_viewers == 2


def test_household_genres_are_summed_over_everyone(overview_store):
    assert collect(overview_store, Apps()).genres == [
        "Adventure", "Action", "Drama", "Reality-TV", "Game-Show"]


def test_library_counts_size_and_this_weeks_additions(overview_store):
    library = collect(overview_store, Apps()).library

    assert (library.movies, library.shows, library.episodes) == (127, 27, 1564)
    assert library.size_bytes == 4_726_229_716_345
    assert (library.added_movies, library.added_episodes) == (0, 8)


def test_request_counts_from_seerr(overview_store):
    requests = collect(overview_store, Apps()).requests

    assert (requests.pending, requests.processing, requests.available, requests.completed) == (
        0, 13, 0, 58)


def test_latest_requests_with_titles_states_and_posters(overview_store):
    latest = collect(overview_store, Apps()).latest_requests

    assert len(latest) == 10
    first, second, third = latest[:3]
    assert (first.title, first.year, first.kind, first.by, first.state) == (
        "VisionQuest", "2026", "tv", "pim", "failed")
    assert first.poster is None  # Sonarr has no series for it
    assert (second.state, second.poster) == ("downloading", "sonarr/53")
    assert (third.kind, third.state, third.poster) == ("movie", "available", "radarr/141")


def test_each_title_is_looked_up_once(overview_store):
    apps = Apps()
    collect(overview_store, apps)
    collect(overview_store, apps)

    lookups = [p for app, p, _ in apps.seen if app == "jellyseerr" and "/request" not in p]
    assert len(lookups) == 10


def test_the_request_states_follow_seerr(overview_store):
    state = media_overview.request_state
    assert state({"status": 1, "media": {"status": 2}}) == "waiting"
    assert state({"status": 2, "media": {"status": 2}}) == "approved"
    assert state({"status": 2, "media": {"status": 3}}) == "downloading"
    assert state({"status": 5, "media": {"status": 4}}) == "partly"
    assert state({"status": 3, "media": {"status": 1}}) == "declined"


def test_one_source_down_leaves_the_other(overview_store):
    result = collect(overview_store, Apps(down=("jellyseerr",)))

    assert result.errors == {"jellyseerr": "HTTP 503"}
    assert result.requests is None and result.library is not None


def test_both_down_raises_so_the_last_answer_goes_stale(overview_store):
    with pytest.raises(RuntimeError):
        collect(overview_store, Apps(down=("tracearr", "jellyseerr")))


def test_needs_a_tracearr_key(overview_store):
    assert media_overview.settings(CFG, overview_store)["enabled"] is True
    no_key = {"widgets": {"host": "nas", "keys": {"jellyseerr": "js-key"}}}
    assert media_overview.settings(no_key, overview_store)["enabled"] is False


def test_the_route_serves_the_answer(overview_store):
    # No `with`: the lifespan would start the scheduler and hit real sources.
    main.app.state.store = overview_store
    main.app.state.config = CFG
    client = TestClient(main.app)
    assert client.get("/api/media/overview").status_code == 503

    overview_store.put_cache(media_overview.CACHE_KEY,
                             collect(overview_store, Apps()).model_dump(mode="json"))

    assert client.get("/api/media/overview").json()["library"]["movies"] == 127


def test_the_poster_route_serves_a_requests_poster(overview_store):
    from app.sources import media_status

    overview_store.put_cache(media_overview.CACHE_KEY,
                             collect(overview_store, Apps()).model_dump(mode="json"))
    cfg = {"widgets": {"host": "nas", "keys": {"sonarr": "s-key"}}}
    seen = []

    def sonarr(request: httpx.Request) -> httpx.Response:
        seen.append(request.url.path)
        return httpx.Response(200, content=b"jpeg", headers={"content-type": "image/jpeg"})

    data, _ = asyncio.run(media_status.poster(cfg, overview_store, "sonarr", 53,
                                              transport=httpx.MockTransport(sonarr)))

    assert data == b"jpeg" and seen == ["/api/v3/mediacover/53/poster-250.jpg"]
    with pytest.raises(LookupError):  # not one of the requests
        asyncio.run(media_status.poster(cfg, overview_store, "sonarr", 999,
                                        transport=httpx.MockTransport(sonarr)))
