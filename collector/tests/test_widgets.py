from __future__ import annotations

import asyncio
import logging

import httpx

from app.models import Service
from app.sources import services as service_catalog
from app.sources import widgets

KEY = "s3cr3t-key"
CFG = {
    "widgets": {
        "host": "nas",
        "keys": {"jellyfin": KEY, "immich": KEY, "jellyseerr": KEY},
    }
}


def _svc(id_: str, widget: str | None, port: int) -> Service:
    return Service(id=id_, name=id_.title(), group="Media", port=port, widget=widget)


def run(store, handler, cfg=CFG):
    return asyncio.run(widgets.collect(cfg, store, transport=httpx.MockTransport(handler)))


def test_jellyfin_counts_streams_and_library_with_the_mediabrowser_header(store):
    store.seed_services([_svc("jellyfin", "jellyfin", 8096)])
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if request.url.path == "/Sessions":
            return httpx.Response(200, json=[
                {"UserName": "pim", "NowPlayingItem": {"Name": "Dune"}},
                {"UserName": "idle"},
                {"UserName": "kid", "NowPlayingItem": {"Name": "Bluey"}},
            ])
        return httpx.Response(200, json={"MovieCount": 812, "SeriesCount": 143})

    result = run(store, handler).items["jellyfin"]

    assert result.error is None
    assert [(s.label, s.value) for s in result.stats] == [
        ("Streaming", 2), ("Movies", 812), ("Series", 143),
    ]
    assert str(seen[0].url) == "http://nas:8096/Sessions?activeWithinSeconds=600"
    assert seen[0].headers["authorization"] == f'MediaBrowser Token="{KEY}"'
    assert "x-emby-token" not in seen[0].headers


def test_immich_reports_counts_and_storage_in_bytes(store):
    store.seed_services([_svc("immich", "immich", 2283)])

    def handler(request):
        assert request.url.path == "/api/server/statistics"
        assert request.headers["x-api-key"] == KEY
        return httpx.Response(
            200,
            json={"photos": 48213, "videos": 1204, "usage": 912_000_000_000,
                  "usagePhotos": 1, "usageVideos": 1, "usageByUser": []},
        )

    stats = run(store, handler).items["immich"].stats

    assert [(s.label, s.value, s.unit) for s in stats] == [
        ("Photos", 48213, "count"), ("Videos", 1204, "count"),
        ("Storage", 912_000_000_000, "bytes"),
    ]


def test_jellyseerr_reports_request_counts(store):
    store.seed_services([_svc("jellyseerr", "jellyseerr", 5055)])

    def handler(request):
        assert request.url.path == "/api/v1/request/count"
        assert request.headers["x-api-key"] == KEY
        return httpx.Response(200, json={"total": 40, "movie": 30, "tv": 10, "pending": 1,
                                         "approved": 3, "declined": 0, "processing": 2,
                                         "available": 35, "completed": 30})

    stats = run(store, handler).items["jellyseerr"].stats

    assert [(s.label, s.value) for s in stats] == [
        ("Pending", 1), ("Processing", 2), ("Available", 35),
    ]


def test_a_missing_key_is_reported_without_calling_the_app(store):
    store.seed_services([_svc("immich", "immich", 2283)])

    def handler(request):
        raise AssertionError("must not be called")

    result = run(store, handler, {"widgets": {"host": "nas", "keys": {"immich": ""}}})

    assert result.items["immich"].error == "No API key set (IMMICH_API_KEY)"


def test_failures_are_short_reasons_and_do_not_affect_other_apps(store):
    store.seed_services([
        _svc("jellyfin", "jellyfin", 8096),
        _svc("immich", "immich", 2283),
        _svc("jellyseerr", "jellyseerr", 5055),
        _svc("dozzle", None, 8081),
    ])

    def handler(request):
        if request.url.port == 8096:
            return httpx.Response(401)
        if request.url.port == 2283:
            raise httpx.ConnectError("refused", request=request)
        return httpx.Response(200, json={"unexpected": True})

    items = run(store, handler).items

    assert items["jellyfin"].error == "API key refused (401)"
    assert items["immich"].error == "Not reachable"
    assert items["jellyseerr"].error == "Unexpected response"
    assert "dozzle" not in items  # no widget, not collected


def test_keys_never_reach_errors_or_logs(store, caplog):
    store.seed_services([_svc("jellyfin", "jellyfin", 8096)])

    def handler(request):
        raise httpx.ConnectError(f"failed for {request.headers['authorization']}", request=request)

    with caplog.at_level(logging.DEBUG):
        result = run(store, handler)

    assert KEY not in (result.items["jellyfin"].error or "")
    assert KEY not in caplog.text


def test_services_carry_stats_or_the_error():
    catalog = [_svc("jellyfin", "jellyfin", 8096), _svc("immich", "immich", 2283),
               _svc("dozzle", None, 8081)]
    cache = {
        "as_of": "2026-09-30T12:00:00+00:00",
        "stale": False,
        "items": {
            "jellyfin": {"stats": [{"label": "Streaming", "value": 2, "unit": "count"}],
                         "error": None},
            "immich": {"stats": [], "error": "Not reachable"},
        },
    }

    result = service_catalog.build(catalog, None, cache)
    by_id = {s.id: s for g in result.groups for s in g.services}

    assert [(s.label, s.value) for s in by_id["jellyfin"].stats] == [("Streaming", 2)]
    assert by_id["immich"].stats is None
    assert by_id["immich"].stats_error == "Not reachable"
    assert by_id["dozzle"].stats is None and by_id["dozzle"].stats_error is None
    assert result.stats_as_of.isoformat() == "2026-09-30T12:00:00+00:00"
