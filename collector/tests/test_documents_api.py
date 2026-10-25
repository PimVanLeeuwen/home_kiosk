from __future__ import annotations

import httpx
import pytest
from fastapi.testclient import TestClient

from app import main
from app.models import Service

CFG = {"widgets": {"host": "nas", "keys": {"paperless": "pl-token"}}}
PAPERLESS = Service(id="paperless", name="Paperless", group="Apps", port=8010, widget="paperless")

DOCS = {"count": 2, "results": [
    {"id": 41, "title": "Jaaropgave 2025", "correspondent": 7, "created": "2026-02-14"},
    {"id": 12, "title": "", "correspondent": None, "created": "2025-03-01T00:00:00+01:00"},
]}
PEOPLE = {"count": 1, "results": [{"id": 7, "name": "Brabant Water"}]}


@pytest.fixture
def client(store):
    main.app.state.store = store
    main.app.state.config = CFG
    yield TestClient(main.app)
    main.app.state.documents_transport = None


def answer(store, handler, services=(PAPERLESS,)):
    store.seed_services(list(services))
    seen: list[httpx.Request] = []

    def record(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return handler(request)

    main.app.state.documents_transport = httpx.MockTransport(record)
    return seen


def paperless(request: httpx.Request) -> httpx.Response:
    return httpx.Response(200, json=DOCS if request.url.path == "/api/documents/" else PEOPLE)


def test_searches_paperless_with_its_token_and_names_the_correspondents(client, store):
    seen = answer(store, paperless)

    body = client.get("/api/documents/search", params={"q": "jaaropgave"}).json()

    assert body["available"] is True and body["stale"] is False
    assert body["results"] == [
        {"id": 41, "title": "Jaaropgave 2025", "correspondent": "Brabant Water",
         "created": "2026-02-14"},
        {"id": 12, "title": "Untitled", "correspondent": None, "created": "2025-03-01"},
    ]
    assert str(seen[0].url).startswith("http://nas:8010/api/documents/?")
    assert seen[0].url.params["query"] == "jaaropgave"
    assert seen[0].url.params["page_size"] == "8"
    assert seen[0].headers["Authorization"] == "Token pl-token"
    assert seen[1].url.params["id__in"] == "7"


def test_no_correspondent_call_without_correspondents(client, store):
    nobody = {"results": [{"id": 1, "title": "Scan", "correspondent": None, "created": None}]}
    seen = answer(store, lambda _: httpx.Response(200, json=nobody))

    body = client.get("/api/documents/search", params={"q": "scan"}).json()

    assert body["results"][0]["created"] is None and len(seen) == 1


def test_paperless_down_is_an_answer_not_an_error(client, store):
    def down(_: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused")

    answer(store, down)
    resp = client.get("/api/documents/search", params={"q": "bill"})

    assert resp.status_code == 200
    assert resp.json() | {"as_of": None} == {
        "as_of": None, "stale": False, "available": False,
        "reason": "Not reachable", "results": []}


def test_a_refused_token_says_so(client, store):
    answer(store, lambda _: httpx.Response(401))

    body = client.get("/api/documents/search", params={"q": "bill"}).json()

    assert body["reason"] == "API key refused (401)"


def test_without_paperless_in_the_catalog_it_is_not_set_up(client, store):
    answer(store, paperless, services=())

    body = client.get("/api/documents/search", params={"q": "bill"}).json()

    assert body["available"] is False and body["reason"] == "Not set up in the hub"


def test_a_query_must_be_two_to_a_hundred_letters(client, store):
    answer(store, paperless)

    assert client.get("/api/documents/search", params={"q": "a"}).status_code == 422
    assert client.get("/api/documents/search", params={"q": "a" * 101}).status_code == 422
