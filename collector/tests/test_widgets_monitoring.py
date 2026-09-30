from __future__ import annotations

import asyncio

import httpx

from app.models import Service
from app.sources import widgets


def collect(store, widget: str, port: int, handler, cfg=None):
    store.seed_services([Service(id=widget, name=widget, group="Monitoring", port=port,
                                 widget=widget)])
    cfg = cfg or {"widgets": {"host": "nas"}}
    result = asyncio.run(widgets.collect(cfg, store, transport=httpx.MockTransport(handler)))
    return result.items[widget]


HEARTBEATS = {
    "heartbeatList": {
        # Oldest first: only the last heartbeat counts.
        "1": [{"status": 0}, {"status": 1}],
        "2": [{"status": 1}, {"status": 0}],
        "3": [{"status": 1}],
        "4": [{"status": 2}],  # pending: neither up nor down
        "5": [],  # no heartbeats yet
    },
    "uptimeList": {"1_24": 0.99, "2_24": 0.97, "3_24": 1.0, "4_24": 0.9, "5_24": 1.0},
}


def test_uptime_kuma_counts_latest_status_and_averages_uptime(store):
    def handler(request):
        assert request.url.path == "/api/status-page/heartbeat/nas"
        return httpx.Response(200, json=HEARTBEATS)

    result = collect(store, "uptimekuma", 3001, handler)

    assert result.error is None  # no key needed
    assert [(s.label, s.value, s.unit) for s in result.stats] == [
        ("Up", 2, "count"), ("Down", 1, "count"), ("Uptime 24h", 97.2, "percent"),
    ]


def test_uptime_kuma_slug_comes_from_widget_options(store):
    paths = []

    def handler(request):
        paths.append(request.url.path)
        return httpx.Response(200, json={"heartbeatList": {}, "uptimeList": {}})

    cfg = {"widgets": {"host": "nas", "options": {"uptimekuma": {"slug": "home"}}}}
    result = collect(store, "uptimekuma", 3001, handler, cfg)

    assert paths == ["/api/status-page/heartbeat/home"]
    # No monitors: no uptime average to show.
    assert [(s.label, s.value) for s in result.stats] == [("Up", 0), ("Down", 0)]


def test_uptime_kuma_unknown_slug_is_a_short_error(store):
    result = collect(store, "uptimekuma", 3001, lambda request: httpx.Response(404))

    assert result.error == "HTTP 404"


def test_scrutiny_counts_disks_by_smart_verdict(store):
    summary = {"data": {"summary": {
        "wwn1": {"device": {"device_name": "sda", "device_status": 0}, "smart": {"temp": 35}},
        "wwn2": {"device": {"device_name": "sdb", "device_status": 1}, "smart": {"temp": 41}},
        "wwn3": {"device": {"device_name": "sdc", "device_status": 2}, "smart": {"temp": 38}},
        "wwn4": {"device": {"device_name": "nvme0", "device_status": 0}, "smart": {}},
    }}}

    def handler(request):
        assert request.url.path == "/api/summary"
        return httpx.Response(200, json=summary)

    result = collect(store, "scrutiny", 8080, handler)

    assert [(s.label, s.value) for s in result.stats] == [
        ("Disks", 4), ("Failed", 1), ("Warnings", 1),
    ]
