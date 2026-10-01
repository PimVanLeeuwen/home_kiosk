from __future__ import annotations

import asyncio
import json

import httpx
import pytest
from fastapi.testclient import TestClient

from app import main
from app.news import html_blocks, saved

BASE = "http://readeck.lan:8084"
CFG = {"readeck": {"base_url": BASE, "api_token": "secret"}}
PNG = b"\x89PNG fake"

ARTICLE = f"""<section>
<h1>Why trains run late</h1>
<p>Most delays start with <a href="https://x">one</a> late train.<br>Then it spreads.</p>
<figure><img src="{BASE}/bm/ab/abc/_resources/one.png" alt="A platform"/>
<figcaption>Utrecht Centraal</figcaption></figure>
<blockquote><p>Punctuality is a network problem.</p></blockquote>
<ul><li>Signals</li><li>Weather <ul><li>Leaves</li></ul></li></ul>
<table><tr><th>Line</th><td>Delay</td></tr></table>
<script>alert(1)</script>
<img src="https://tracker.example/pixel.png"/>
</section>"""


def bookmark(bid="abc", **extra):
    raw = {
        "id": bid, "url": f"https://news.example/{bid}", "title": f"Story {bid}",
        "site_name": "News", "created": "2026-09-30T10:00:00Z", "published": None,
        "description": "", "reading_time": 4, "read_progress": 0, "is_archived": False,
        "is_deleted": False, "loaded": True, "state": 0, "has_article": True,
        "resources": {"thumbnail": {"src": f"{BASE}/bm/ab/{bid}/_resources/thumb.png"}},
    }
    return {**raw, **extra}


class FakeReadeck:
    def __init__(self):
        self.requests: list[httpx.Request] = []
        self.status = 200

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        assert request.headers["authorization"] == "Bearer secret"
        if self.status != 200:
            return httpx.Response(self.status)
        path = request.url.path
        if path == "/api/bookmarks":
            items = [bookmark("abc"), bookmark("gone", is_deleted=True),
                     bookmark("busy", loaded=False, resources={})]
            return httpx.Response(200, json=items, headers={"Total-Count": "3"})
        if path in ("/api/bookmarks/abc", "/api/bookmarks/busy"):
            if request.method == "PATCH":
                return httpx.Response(200, json=json.loads(request.content))
            bid = path.rsplit("/", 1)[1]
            if bid == "busy":
                return httpx.Response(200, json=bookmark(bid, loaded=False, resources={}))
            return httpx.Response(200, json=bookmark(bid))
        if path == "/api/bookmarks/abc/article":
            return httpx.Response(200, text=ARTICLE, headers={"content-type": "text/html"})
        if path.startswith("/bm/"):
            return httpx.Response(200, content=PNG, headers={"content-type": "image/png"})
        return httpx.Response(404)


@pytest.fixture
def fake():
    saved._images.clear()
    return FakeReadeck()


@pytest.fixture
def client(store, fake):
    main.app.state.store = store
    main.app.state.config = CFG
    main.app.state.readeck_transport = httpx.MockTransport(fake)
    yield TestClient(main.app, headers={"origin": "http://testserver"})
    del main.app.state.readeck_transport


# --- html to blocks --------------------------------------------------------------------


def test_html_blocks_keep_text_only():
    blocks, images = html_blocks.to_blocks(ARTICLE)
    assert [(b.type, b.text or b.items) for b in blocks] == [
        ("heading", "Why trains run late"),
        ("paragraph", "Most delays start with one late train. Then it spreads."),
        ("image", "A platform"),
        ("paragraph", "Utrecht Centraal"),
        ("quote", "Punctuality is a network problem."),
        ("list", ["Signals", "Weather", "Leaves"]),
        ("paragraph", "Line · Delay"),
        ("image", []),
    ]
    assert images == [f"{BASE}/bm/ab/abc/_resources/one.png", "https://tracker.example/pixel.png"]


def test_html_blocks_handle_loose_text_and_unclosed_tags():
    blocks, _ = html_blocks.to_blocks("Loose text <p>open paragraph <ul><li>item")
    assert [(b.type, b.text or b.items) for b in blocks] == [
        ("paragraph", "Loose text"), ("paragraph", "open paragraph"), ("list", ["item"])]


# --- readeck client -----------------------------------------------------------------------


def test_bookmarks_skip_deleted_and_flag_unreadable(fake):
    items, total = asyncio.run(saved.bookmarks(CFG, transport=httpx.MockTransport(fake)))
    assert [(b.id, b.readable, b.thumbnail) for b in items] == [
        ("abc", True, True), ("busy", False, False)]
    assert total == 3
    params = fake.requests[0].url.params
    assert params["is_archived"] == "false" and params["sort"] == "-created"


def test_missing_config_and_rejected_token_read_as_sentences(fake):
    with pytest.raises(saved.ReadeckError, match="not configured"):
        asyncio.run(saved.bookmarks({}))
    fake.status = 401
    with pytest.raises(saved.ReadeckError, match="rejected the token"):
        asyncio.run(saved.bookmarks(CFG, transport=httpx.MockTransport(fake)))


# --- endpoints ----------------------------------------------------------------------------


def test_list_endpoint(client):
    body = client.get("/api/saved").json()
    assert body["total"] == 3
    assert body["bookmarks"][0]["title"] == "Story abc"
    assert "secret" not in json.dumps(body)


def test_content_endpoint_proxies_only_readeck_images(client):
    body = client.get("/api/saved/abc/content").json()
    assert body["ok"] and body["title"] == "Story abc"
    pictures = [b for b in body["blocks"] if b["type"] == "image"]
    assert [p["src"] for p in pictures] == ["/api/saved/abc/images/0", "/api/saved/abc/images/1"]
    assert "images" not in body and "readeck.lan" not in json.dumps(body)

    resp = client.get("/api/saved/abc/images/0")
    assert resp.status_code == 200 and resp.content == PNG
    assert resp.headers["x-content-type-options"] == "nosniff"
    # The tracker pixel is not on Readeck's origin, so the hub won't fetch it.
    assert client.get("/api/saved/abc/images/1").status_code == 404
    assert client.get("/api/saved/abc/images/9").status_code == 404


def test_image_endpoint_works_after_a_restart(client, fake):
    # The image list is in memory only; without it the article is read again.
    assert client.get("/api/saved/abc/images/0").content == PNG


def test_unreadable_bookmark_offers_the_original(client):
    body = client.get("/api/saved/busy/content").json()
    assert body["ok"] is False and "no readable text" in body["reason"]


def test_thumbnail_endpoint(client):
    resp = client.get("/api/saved/abc/thumbnail")
    assert resp.status_code == 200 and resp.content == PNG
    assert client.get("/api/saved/busy/thumbnail").status_code == 404


def test_archive_progress_and_delete_patch_readeck(client, fake):
    assert client.patch("/api/saved/abc", json={"archived": True}).json() == {"archived": True}
    assert client.patch("/api/saved/abc", json={"progress": 40}).status_code == 200
    assert client.delete("/api/saved/abc").json() == {"deleted": True}
    patches = [json.loads(r.content) for r in fake.requests if r.method == "PATCH"]
    assert patches == [{"is_archived": True}, {"read_progress": 40}, {"is_deleted": True}]


def test_updates_are_validated(client, fake):
    assert client.patch("/api/saved/abc", json={}).status_code == 422
    assert client.patch("/api/saved/abc", json={"progress": 140}).status_code == 422
    assert client.patch("/api/saved/a.b%2F..", json={"archived": True}).status_code == 404
    assert client.get("/api/saved/nope!/content").status_code == 404
    assert not any(r.method == "PATCH" for r in fake.requests)


def test_writes_need_the_same_origin(client):
    other = TestClient(main.app, headers={"origin": "https://evil.example"})
    assert other.delete("/api/saved/abc").status_code == 403


def test_readeck_errors_map_to_status_codes(client, fake):
    fake.status = 500
    resp = client.get("/api/saved")
    assert resp.status_code == 502 and resp.json()["detail"] == "Readeck error 500"
    fake.status = 404
    assert client.get("/api/saved/abc/content").status_code == 404
