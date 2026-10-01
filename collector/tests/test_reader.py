from __future__ import annotations

import asyncio
import socket
from datetime import UTC, datetime

import httpx
import pytest
from fastapi.testclient import TestClient

from app import main
from app.news import reader
from app.news import store as news

NOW = datetime(2026, 10, 1, 12, 0, tzinfo=UTC)
URL = "https://news.example/story"
AID = news.article_id(URL)

PARAGRAPH = "The council approved the new bike lanes after a long debate on Tuesday. " * 3
PAGE = f"""<!doctype html><html><head><title>Bike lanes approved</title>
<meta name="author" content="Jane Writer"></head><body>
<nav><a href="/">Home</a> <a href="/sport">Sport</a></nav>
<article>
<h1>Bike lanes approved</h1>
<p>{PARAGRAPH}</p>
<h2>What happens next</h2>
<p>{PARAGRAPH.replace("council", "city")}<script>alert("x")</script></p>
<img src="https://cdn.news.example/lanes.jpg" alt="A new bike lane">
<blockquote>Cycling is the future of this city, said the alderman to reporters.</blockquote>
<ul><li>Work starts in spring next year</li><li>It costs four million euros</li></ul>
<p>{PARAGRAPH.replace("Tuesday", "Wednesday")}</p>
</article>
<footer>Copyright</footer></body></html>"""

JPEG = b"\xff\xd8\xff\xe0fake-jpeg"


@pytest.fixture(autouse=True)
def public_dns(monkeypatch):
    """Every *.example host resolves to a public address; 'intranet' to the LAN."""
    def fake(host, port, *args, **kwargs):
        address = "192.168.1.10" if host.startswith("intranet") else "93.184.215.14"
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (address, port))]
    monkeypatch.setattr(socket, "getaddrinfo", fake)


def handler(request: httpx.Request) -> httpx.Response:
    if request.url.path == "/story":
        return httpx.Response(200, text=PAGE, headers={"content-type": "text/html"})
    if request.url.path == "/lanes.jpg":
        return httpx.Response(200, content=JPEG, headers={"content-type": "image/jpeg"})
    if request.url.path == "/moved":
        return httpx.Response(302, headers={"location": "http://intranet.lan/admin"})
    if request.url.path == "/thin":
        return httpx.Response(200, text="<html><body><p>Subscribe.</p></body></html>")
    if request.url.path == "/logo.svg":
        return httpx.Response(200, text="<svg/>", headers={"content-type": "image/svg+xml"})
    return httpx.Response(404)


@pytest.fixture
def client(store):
    news.ensure_tables(store)
    news.save_articles(store, "nl", [
        {"url": URL, "title": "Bike lanes", "source": "News", "published": NOW},
        {"url": "https://news.example/moved", "title": "Moved", "source": "News",
         "published": NOW},
    ], NOW)
    main.app.state.store = store
    main.app.state.reader_transport = httpx.MockTransport(handler)
    yield TestClient(main.app, headers={"origin": "http://testserver"})
    del main.app.state.reader_transport


# --- extraction ------------------------------------------------------------------------


def test_extract_turns_a_page_into_plain_blocks():
    content = asyncio.run(reader.extract(URL, AID, httpx.MockTransport(handler)))

    assert content.ok
    assert content.title == "Bike lanes approved"
    kinds = [b.type for b in content.blocks]
    assert kinds.count("paragraph") == 3
    assert "heading" in kinds and "quote" in kinds and "list" in kinds and "image" in kinds
    assert next(b for b in content.blocks if b.type == "heading").text == "What happens next"
    assert next(b for b in content.blocks if b.type == "list").items == [
        "Work starts in spring next year", "It costs four million euros"]
    picture = next(b for b in content.blocks if b.type == "image")
    assert picture.src == f"/api/news/articles/{AID}/images/0"
    assert picture.text == "A new bike lane"
    assert content.images == ["https://cdn.news.example/lanes.jpg"]
    text = " ".join(b.text for b in content.blocks)
    assert "alert(" not in text and "Copyright" not in text and "<" not in text


def test_to_blocks_flattens_markup_to_text(monkeypatch):
    monkeypatch.setattr(reader, "MIN_TEXT_CHARS", 1)
    xml = ('<doc title="T"><main><p>Hello <hi rend="#b">bold</hi> world</p>'
           '<head rend="h2"><ref target="https://x">Link</ref> title</head>'
           '<graphic src="javascript:alert(1)" alt="bad"/></main></doc>')
    content = reader.to_blocks(xml, "abc")
    assert [(b.type, b.text) for b in content.blocks] == [
        ("paragraph", "Hello bold world"), ("heading", "Link title")]
    assert content.images == []


def test_to_blocks_without_paragraphs_is_not_readable():
    content = reader.to_blocks('<doc><main><head>Only a title</head></main></doc>', "abc")
    assert not content.ok and "No readable text" in content.reason


def test_extract_reports_unreadable_pages():
    transport = httpx.MockTransport(handler)
    thin = asyncio.run(reader.extract("https://news.example/thin", "a", transport))
    assert not thin.ok and "No readable text" in thin.reason

    gone = asyncio.run(reader.extract("https://news.example/gone", "a", transport))
    assert not gone.ok and gone.reason == "The site answered 404"


def test_extract_refuses_private_addresses_and_redirects_to_them():
    transport = httpx.MockTransport(handler)
    direct = asyncio.run(reader.extract("http://intranet.lan/admin", "a", transport))
    assert not direct.ok and direct.reason.startswith("Blocked")

    redirected = asyncio.run(reader.extract("https://news.example/moved", "a", transport))
    assert not redirected.ok and redirected.reason.startswith("Blocked")

    other_scheme = asyncio.run(reader.extract("file:///etc/passwd", "a", transport))
    assert not other_scheme.ok and other_scheme.reason.startswith("Blocked")


def test_extract_caps_the_page_size(monkeypatch):
    monkeypatch.setattr(reader, "MAX_PAGE_BYTES", 100)
    content = asyncio.run(reader.extract(URL, AID, httpx.MockTransport(handler)))
    assert not content.ok and content.reason == "The page is too large"


def test_image_only_accepts_raster_images():
    transport = httpx.MockTransport(handler)
    assert asyncio.run(reader.image("https://cdn.news.example/lanes.jpg", transport)) == (
        JPEG, "image/jpeg")
    with pytest.raises(ValueError):
        asyncio.run(reader.image("https://cdn.news.example/logo.svg", transport))
    with pytest.raises(reader.Blocked):
        asyncio.run(reader.image("http://intranet.lan/cam.jpg", transport))


# --- endpoints -----------------------------------------------------------------------------


def test_content_endpoint_extracts_once_and_hides_image_urls(client, store):
    first = client.get(f"/api/news/articles/{AID}/content")
    assert first.status_code == 200
    body = first.json()
    assert body["ok"] and body["title"] == "Bike lanes approved"
    assert "images" not in body
    assert "cdn.news.example" not in first.text

    # Served from the cache now, even with the site gone.
    main.app.state.reader_transport = httpx.MockTransport(lambda r: httpx.Response(500))
    assert client.get(f"/api/news/articles/{AID}/content").json() == body


def test_content_endpoint_explains_failures_and_retries_later(client):
    moved = news.article_id("https://news.example/moved")
    body = client.get(f"/api/news/articles/{moved}/content").json()
    assert body["ok"] is False and body["reason"].startswith("Blocked")
    assert reader.cached(main.app.state.store, moved) is None
    assert client.get("/api/news/articles/nope/content").status_code == 404


def test_image_endpoint_serves_only_listed_images(client):
    assert client.get(f"/api/news/articles/{AID}/images/0").status_code == 404  # not read yet
    client.get(f"/api/news/articles/{AID}/content")

    resp = client.get(f"/api/news/articles/{AID}/images/0")
    assert resp.status_code == 200
    assert resp.content == JPEG
    assert resp.headers["content-type"] == "image/jpeg"
    assert resp.headers["x-content-type-options"] == "nosniff"
    assert "max-age" in resp.headers["cache-control"]
    assert client.get(f"/api/news/articles/{AID}/images/1").status_code == 404
    assert client.get(f"/api/news/articles/{AID}/images/-1").status_code == 404


def test_image_endpoint_reports_upstream_failures(client):
    client.get(f"/api/news/articles/{AID}/content")
    main.app.state.reader_transport = httpx.MockTransport(lambda r: httpx.Response(500))
    assert client.get(f"/api/news/articles/{AID}/images/0").status_code == 502


def test_content_is_pruned_with_its_article(store):
    news.ensure_tables(store)
    old = datetime(2026, 9, 1, tzinfo=UTC)
    news.save_articles(store, "nl", [
        {"url": URL, "title": "Old", "source": "News", "published": old}], old)
    reader.remember(store, AID, reader.ArticleContent(
        ok=True, blocks=[reader.Block(type="paragraph", text="x")]))
    assert reader.cached(store, AID) is not None

    news.prune(store, NOW)
    assert reader.cached(store, AID) is None
