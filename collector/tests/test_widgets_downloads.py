from __future__ import annotations

import asyncio
import json
import logging

import httpx
import pytest

import app.main  # noqa: F401  (applies the httpx log level under test)
from app.models import Service
from app.sources import widgets
from app.sources.widgets import downloads


@pytest.fixture(autouse=True)
def no_dns(monkeypatch):
    """No real lookups in tests: a name stays a name unless a test resolves it."""
    async def unknown(host, port):
        raise OSError("no such host")

    monkeypatch.setattr(downloads, "_lookup", unknown)

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


def rpc_handler(seen):
    def handler(request):
        seen.append(request)
        if "x-transmission-session-id" not in request.headers:
            return httpx.Response(409, headers={"X-Transmission-Session-Id": "abc"})
        return httpx.Response(200, json={"jsonrpc": "2.0", "id": 1, "result": {
            "active_torrent_count": 1, "download_speed": 0, "upload_speed": 5}})
    return handler


def test_transmission_is_called_by_address_not_by_name(store, monkeypatch):
    # Transmission answers a name outside its rpc-host-whitelist with 421, and
    # host.docker.internal is one: the collector calls the address instead.
    async def resolve(host, port):
        assert (host, port) == ("host.docker.internal", 9091)
        return "172.17.0.1"

    monkeypatch.setattr(downloads, "_lookup", resolve)
    seen = []
    result = collect(store, "transmission", 9091, rpc_handler(seen),
                     {"widgets": {"host": "host.docker.internal"}})

    assert result.error is None and result.stats[0].value == 1
    assert {(r.url.host, r.url.port) for r in seen} == {("172.17.0.1", 9091)}


def test_an_address_is_used_as_it_is(store, monkeypatch):
    async def must_not(host, port):
        pytest.fail("an address needs no lookup")

    monkeypatch.setattr(downloads, "_lookup", must_not)
    seen = []
    collect(store, "transmission", 9091, rpc_handler(seen), {"widgets": {"host": "100.64.0.1"}})
    assert {r.url.host for r in seen} == {"100.64.0.1"}


def test_a_refused_request_logs_its_status(store, caplog):
    with caplog.at_level(logging.WARNING):
        result = collect(store, "transmission", 9091, lambda request: httpx.Response(421),
                         {"widgets": {"host": "nas"}})
    assert result.error == "HTTP 421"
    assert "HTTPStatusError 421" in caplog.text

