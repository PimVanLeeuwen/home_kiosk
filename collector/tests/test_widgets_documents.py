from __future__ import annotations

import asyncio

import httpx

from app.models import Service
from app.sources import widgets

KEY = "pl-token"
CFG = {"widgets": {"host": "nas", "keys": {"paperless": KEY}}}

STATS = {
    "documents_total": 412,
    "documents_inbox": 7,
    "inbox_tag": 3,
    "inbox_tags": [3],
    "document_file_type_counts": [],
    "character_count": 1,
    "tag_count": 9,
    "correspondent_count": 134,
    "document_type_count": 10,
    "storage_path_count": 0,
    "current_asn": 0,
}


def run(store, handler, cfg=CFG):
    service = Service(id="paperless", name="Paperless", group="Apps", port=8010, widget="paperless")
    store.seed_services([service])
    return asyncio.run(widgets.collect(cfg, store, transport=httpx.MockTransport(handler)))


def test_paperless_counts_documents_inbox_and_correspondents_with_its_token(store):
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json=STATS)

    result = run(store, handler).items["paperless"]

    assert [(s.label, s.value) for s in result.stats] == [
        ("Documents", 412), ("Inbox", 7), ("Correspondents", 134),
    ]
    assert str(seen[0].url) == "http://nas:8010/api/statistics/"
    assert seen[0].headers["Authorization"] == f"Token {KEY}"


def test_paperless_leaves_the_inbox_out_without_an_inbox_tag(store):
    no_inbox = STATS | {"documents_inbox": None}
    result = run(store, lambda _: httpx.Response(200, json=no_inbox)).items["paperless"]

    assert [s.label for s in result.stats] == ["Documents", "Correspondents"]


def test_paperless_says_when_the_token_is_refused(store):
    result = run(store, lambda _: httpx.Response(401)).items["paperless"]

    assert result.stats == [] and result.error == "API key refused (401)"


def test_paperless_without_a_token_asks_for_one(store):
    no_key = {"widgets": {"host": "nas"}}
    result = run(store, lambda _: httpx.Response(200, json=STATS), cfg=no_key).items["paperless"]

    assert result.error == "No API key set (PAPERLESS_API_KEY)"
