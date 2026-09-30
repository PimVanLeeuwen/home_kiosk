from __future__ import annotations

import asyncio
import json
import logging

import httpx

import app.main  # noqa: F401  (applies the httpx log level under test)
from app.models import Service
from app.sources import widgets

KEY = "sab-key-123"
CFG = {"widgets": {"host": "nas", "keys": {"sabnzbd": KEY}}}


def collect(store, widget: str, port: int, handler, cfg=CFG):
    store.seed_services([Service(id=widget, name=widget, group="Downloads", port=port,
                                 widget=widget)])
    result = asyncio.run(widgets.collect(cfg, store, transport=httpx.MockTransport(handler)))
    return result.items[widget]


SAB_QUEUE = {"queue": {"noofslots": 3, "kbpersec": "2048.00", "mbleft": "1536.00",
                       "status": "Downloading", "paused": False}}


def test_sabnzbd_reads_the_queue(store):
    def handler(request):
        assert request.url.path == "/api"
        assert dict(request.url.params) == {"mode": "queue", "output": "json", "apikey": KEY}
        return httpx.Response(200, json=SAB_QUEUE)

    result = collect(store, "sabnzbd", 8085, handler)

    assert [(s.label, s.value, s.unit) for s in result.stats] == [
        ("Queued", 3, "count"),
        ("Down", 2048 * 1024, "bytes_per_second"),
        ("Left", 1536 * 1024 * 1024, "bytes"),
    ]


def test_sabnzbd_key_in_the_url_never_reaches_the_log(store, caplog):
    # SABnzbd only takes the key as a query parameter; httpx would log the URL.
    with caplog.at_level(logging.INFO):
        collect(store, "sabnzbd", 8085, lambda request: httpx.Response(200, json=SAB_QUEUE))
        store2_result = collect(store, "sabnzbd", 8085, lambda request: httpx.Response(500))

    assert store2_result.error == "HTTP 500"
    assert KEY not in caplog.text


def test_transmission_speaks_json_rpc_after_the_session_handshake(store):
    requests = []

    def handler(request):
        requests.append(request)
        if "x-transmission-session-id" not in request.headers:
            return httpx.Response(409, headers={"X-Transmission-Session-Id": "abc"})
        assert request.headers["x-transmission-session-id"] == "abc"
        body = json.loads(request.content)
        assert body == {"jsonrpc": "2.0", "method": "session_stats", "id": 1}
        return httpx.Response(200, json={"jsonrpc": "2.0", "id": 1, "result": {
            "active_torrent_count": 2, "download_speed": 5_000_000, "upload_speed": 250_000,
            "paused_torrent_count": 7, "torrent_count": 9}})

    result = collect(store, "transmission", 9091, handler, {"widgets": {"host": "nas"}})

    assert result.error is None  # no key needed
    assert [(s.label, s.value) for s in result.stats] == [
        ("Active", 2), ("Down", 5_000_000), ("Up", 250_000),
    ]
    assert [r.url.path for r in requests] == ["/transmission/rpc", "/transmission/rpc"]


def test_transmission_falls_back_to_the_pre_4_1_protocol(store):
    def handler(request):
        body = json.loads(request.content)
        if body.get("jsonrpc"):
            # 4.0 does not know JSON-RPC or the snake_case method.
            return httpx.Response(200, json={"result": "method name not recognized",
                                             "arguments": {}})
        assert body == {"method": "session-stats"}
        return httpx.Response(200, json={"result": "success", "arguments": {
            "activeTorrentCount": 1, "downloadSpeed": 100, "uploadSpeed": 50}})

    result = collect(store, "transmission", 9091, handler, {"widgets": {"host": "nas"}})

    assert [(s.label, s.value) for s in result.stats] == [("Active", 1), ("Down", 100), ("Up", 50)]


def test_transmission_refusing_the_handshake_is_an_error(store):
    result = collect(store, "transmission", 9091, lambda request: httpx.Response(409),
                     {"widgets": {"host": "nas"}})

    assert result.error == "HTTP 409"
