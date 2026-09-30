from __future__ import annotations

import asyncio

import httpx
import pytest

from app.models import Service
from app.sources import widgets

KEY = "arr-key"
CFG = {
    "widgets": {
        "host": "nas",
        "keys": {"sonarr": KEY, "radarr": KEY, "bazarr": KEY, "prowlarr": KEY},
    }
}


def collect(store, widget: str, port: int, handler):
    store.seed_services([Service(id=widget, name=widget, group="Arr", port=port, widget=widget)])
    result = asyncio.run(widgets.collect(CFG, store, transport=httpx.MockTransport(handler)))
    return result.items[widget]


@pytest.mark.parametrize(("widget", "port"), [("sonarr", 8989), ("radarr", 7878)])
def test_sonarr_and_radarr_read_queue_and_missing_totals(store, widget, port):
    seen = []

    def handler(request):
        seen.append(request)
        assert request.headers["x-api-key"] == KEY
        if request.url.path == "/api/v3/queue/status":
            return httpx.Response(200, json={"totalCount": 3, "count": 3, "errors": False})
        assert request.url.path == "/api/v3/wanted/missing"
        # Only one row requested: the total is all that is needed.
        assert request.url.params["pageSize"] == "1"
        return httpx.Response(200, json={"page": 1, "pageSize": 1, "totalRecords": 41,
                                         "records": [{}]})

    result = collect(store, widget, port, handler)

    assert result.error is None
    assert [(s.label, s.value) for s in result.stats] == [("Queued", 3), ("Missing", 41)]
    assert {r.url.port for r in seen} == {port}


def test_bazarr_reports_missing_subtitles(store):
    def handler(request):
        assert request.url.path == "/api/badges"
        assert request.headers["x-api-key"] == KEY
        return httpx.Response(200, json={"episodes": 12, "movies": 4, "providers": 0,
                                         "status": 0})

    result = collect(store, "bazarr", 6767, handler)

    assert [(s.label, s.value) for s in result.stats] == [
        ("Episodes missing", 12), ("Movies missing", 4),
    ]


def test_prowlarr_counts_enabled_indexers_and_sums_stats(store):
    def handler(request):
        assert request.headers["x-api-key"] == KEY
        if request.url.path == "/api/v1/indexer":
            return httpx.Response(200, json=[{"id": 1, "enable": True}, {"id": 2, "enable": False},
                                             {"id": 3, "enable": True}])
        assert request.url.path == "/api/v1/indexerstats"
        return httpx.Response(200, json={"indexers": [
            {"indexerId": 1, "numberOfGrabs": 10, "numberOfQueries": 300},
            {"indexerId": 3, "numberOfGrabs": 5, "numberOfQueries": 120},
        ], "userAgents": [], "hosts": []})

    result = collect(store, "prowlarr", 9696, handler)

    assert [(s.label, s.value) for s in result.stats] == [
        ("Indexers", 2), ("Grabs", 15), ("Queries", 420),
    ]


def test_an_unexpected_shape_is_reported_not_raised(store):
    result = collect(store, "sonarr", 8989, lambda request: httpx.Response(200, json=[]))

    assert result.error == "Unexpected response"
