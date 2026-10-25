from __future__ import annotations

import asyncio
import base64

import httpx

from app.models import Service
from app.sources import widgets

KEY = "hub-password"
CFG = {"widgets": {"host": "nas", "keys": {"adguard": KEY}}}

# Trimmed from a running AdGuard v0.107.79.
STATS = {
    "time_units": "hours",
    "top_queried_domains": [{"example.com": 2}],
    "top_clients": [{"192.168.1.20": 8}],
    "top_blocked_domains": [{"doubleclick.net": 3}],
    "dns_queries": [0] * 23 + [800],
    "blocked_filtering": [0] * 23 + [96],
    "num_dns_queries": 800,
    "num_blocked_filtering": 96,
    "num_replaced_safebrowsing": 0,
    "num_replaced_safesearch": 0,
    "num_replaced_parental": 0,
    "avg_processing_time": 0.02,
}


def run(store, handler, cfg=CFG):
    service = Service(id="adguard", name="AdGuard Home", group="Monitoring", port=8053,
                      widget="adguard")
    store.seed_services([service])
    return asyncio.run(widgets.collect(cfg, store, transport=httpx.MockTransport(handler)))


def test_adguard_counts_queries_and_the_share_blocked_as_the_hub_user(store):
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json=STATS)

    result = run(store, handler).items["adguard"]

    assert [(s.label, s.value, s.unit) for s in result.stats] == [
        ("Queries 24h", 800, "count"), ("Blocked", 96, "count"), ("Share blocked", 12.0, "percent"),
    ]
    assert str(seen[0].url) == "http://nas:8053/control/stats"
    token = base64.b64encode(f"hub:{KEY}".encode()).decode()
    assert seen[0].headers["Authorization"] == f"Basic {token}"


def test_adguard_user_can_be_set_in_the_options(store):
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json=STATS)

    options = {"options": {"adguard": {"user": "kiosk"}}}
    run(store, handler, {"widgets": CFG["widgets"] | options})

    assert base64.b64decode(seen[0].headers["Authorization"].split()[1]).decode() == f"kiosk:{KEY}"


def test_adguard_leaves_the_share_out_before_any_query(store):
    empty = STATS | {"num_dns_queries": 0, "num_blocked_filtering": 0}
    result = run(store, lambda _: httpx.Response(200, json=empty)).items["adguard"]

    assert [s.label for s in result.stats] == ["Queries 24h", "Blocked"]


def test_adguard_says_when_the_password_is_refused(store):
    result = run(store, lambda _: httpx.Response(401)).items["adguard"]

    assert result.stats == [] and result.error == "API key refused (401)"


def test_adguard_without_a_password_names_the_env_variable(store):
    result = run(store, lambda _: httpx.Response(200, json=STATS),
                 {"widgets": {"host": "nas", "keys": {}}}).items["adguard"]

    assert result.error == "No API key set (ADGUARD_API_KEY)"
