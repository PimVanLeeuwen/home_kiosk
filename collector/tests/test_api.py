from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app import main
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


@pytest.mark.parametrize("path", ["/api/portfolio", "/api/spotlight", "/api/news", "/api/nas"])
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
    ],
)
def test_serves_the_cached_payload_including_stale_flag(client, store, path, key):
    store.put_cache(key, {"as_of": "2026-09-30T12:00:00Z", "stale": True})

    resp = client.get(path)

    assert resp.status_code == 200
    assert resp.json() == {"as_of": "2026-09-30T12:00:00Z", "stale": True}


def test_save_rejects_a_non_url(client):
    assert client.post("/api/save", json={"url": "not a url"}).status_code == 422
