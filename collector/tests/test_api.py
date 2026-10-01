from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app import main
from app.models import Service
from app.sources import feeds


@pytest.fixture
def client(store):
    # No `with`: the lifespan would start the scheduler and hit real sources.
    main.app.state.store = store
    main.app.state.config = {}
    return TestClient(main.app)


def test_health_on_both_paths(client):
    assert client.get("/health").json() == {"status": "ok"}
    assert client.get("/api/health").json() == {"status": "ok"}


@pytest.mark.parametrize(
    "path", ["/api/portfolio", "/api/spotlight", "/api/news", "/api/nas", "/api/hosts"]
)
def test_cold_start_is_503_with_a_reason(client, path):
    resp = client.get(path)

    assert resp.status_code == 503
    assert "no " in resp.json()["detail"]


@pytest.mark.parametrize(
    ("path", "key"),
    [
        ("/api/portfolio", "portfolio"),
        ("/api/spotlight", "spotlight"),
        ("/api/news", "news"),
        ("/api/news/full", feeds.FULL_CACHE_KEY),
        ("/api/nas", "nas"),
        ("/api/hosts", "hosts"),
    ],
)
def test_serves_the_cached_payload_including_stale_flag(client, store, path, key):
    store.put_cache(key, {"as_of": "2026-09-30T12:00:00Z", "stale": True})

    resp = client.get(path)

    assert resp.status_code == 200
    assert resp.json() == {"as_of": "2026-09-30T12:00:00Z", "stale": True}


def test_save_rejects_a_non_url(client):
    assert client.post("/api/save", json={"url": "not a url"}).status_code == 422


def test_services_without_container_list_reads_unknown(client, store):
    store.seed_services([Service(id="jellyfin", name="Jellyfin", group="Media", port=8096,
                                 container="jellyfin")])

    body = client.get("/api/services").json()

    assert body["stale"] is True
    assert body["as_of"] is None
    assert body["groups"][0]["services"][0] == {
        "id": "jellyfin",
        "name": "Jellyfin",
        "group": "Media",
        "description": "",
        "port": 8096,
        "path": "/",
        "url": None,
        "container": "jellyfin",
        "widget": None,
        "icon": None,
        "status": "unknown",
        "stats": None,
        "stats_error": None,
    }


def test_services_with_container_list(client, store):
    store.seed_services([Service(id="sonarr", name="Sonarr", group="Arr", port=8989,
                                 container="sonarr")])
    store.put_cache("containers", {
        "as_of": "2026-09-30T12:00:00+00:00",
        "stale": False,
        "containers": [{"name": "sonarr", "state": "exited", "health": None}],
    })

    body = client.get("/api/services").json()

    assert body["stale"] is False
    assert body["groups"][0]["services"][0]["status"] == "down"


def test_repos_serves_the_cached_payload(client, store):
    assert client.get("/api/repos").status_code == 503
    store.put_cache("repos", {"as_of": "2026-09-30T12:00:00+00:00", "stale": False, "groups": []})

    assert client.get("/api/repos").json()["groups"] == []
