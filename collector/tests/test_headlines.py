from __future__ import annotations

import asyncio
import io
import socket
from datetime import UTC, datetime, timedelta

import feedparser
import httpx
import pytest
from fastapi.testclient import TestClient
from PIL import Image, UnidentifiedImageError

from app import main
from app.news import headlines
from app.news import store as news
from app.sources import feeds

NOW = datetime(2026, 10, 14, 16, 0, tzinfo=UTC)


def picture(width: int, height: int, kind: str = "JPEG") -> bytes:
    out = io.BytesIO()
    Image.new("RGB", (width, height), (90, 120, 200)).save(out, kind)
    return out.getvalue()


@pytest.fixture(autouse=True)
def public_dns(monkeypatch):
    def fake(host, port, *args, **kwargs):
        address = "192.168.1.10" if host.startswith("intranet") else "93.184.215.14"
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (address, port))]
    monkeypatch.setattr(socket, "getaddrinfo", fake)


# --- a feed entry's picture and summary -------------------------------------------------


def entry(xml_item: str):
    feed = f"""<rss version="2.0" xmlns:media="http://search.yahoo.com/mrss/"><channel>
      <item><title>T</title><link>https://news.example/a</link>{xml_item}</item></channel></rss>"""
    return feedparser.parse(feed).entries[0]


def test_the_feeds_picture_is_the_widest_media_or_an_enclosure_or_an_img():
    media = entry('<media:content url="https://i.example/s.jpg" width="320" medium="image"/>'
                  '<media:content url="https://i.example/l.jpg" width="1280" medium="image"/>'
                  '<media:content url="https://i.example/v.mp4" width="1920" medium="video"/>')
    enclosure = entry('<enclosure url="https://i.example/e.jpg" type="image/jpeg" length="1"/>')
    body = entry("<description>&lt;p&gt;Hi &lt;img src=&quot;https://i.example/b.jpg?a=1&amp;"
                 "b=2&quot;&gt;&lt;/p&gt;</description>")

    assert feeds._image(media) == "https://i.example/l.jpg"
    assert feeds._image(enclosure) == "https://i.example/e.jpg"
    assert feeds._image(body) == "https://i.example/b.jpg?a=1&b=2"
    assert feeds._image(entry("<description>No picture</description>")) is None


def test_the_summary_is_plain_text_and_none_for_hacker_news():
    long = "&lt;p&gt;Het kabinet &amp;amp; de Kamer&lt;/p&gt; " + "woord " * 80

    summary = feeds._summary(entry(f"<description>{long}</description>"))

    assert summary.startswith("Het kabinet & de Kamer woord")
    assert len(summary) <= feeds.SUMMARY_MAX_CHARS + 1 and summary.endswith("…")
    hn = entry("<description>&lt;p&gt;Article URL: https://x.example&lt;/p&gt;</description>")
    assert feeds._summary(hn) is None


# --- pictures ---------------------------------------------------------------------------


def test_finds_the_pages_og_image_in_either_attribute_order():
    page = """<head><meta name="twitter:image" content="https://t.example/t.jpg">
      <meta content="/img/og.jpg?a=1&amp;b=2" property="og:image"></head>"""

    assert headlines.page_image(page, "https://news.example/story") == (
        "https://news.example/img/og.jpg?a=1&b=2")
    assert headlines.page_image("<meta name='twitter:image' content='t.jpg'>",
                                "https://news.example/") == "https://news.example/t.jpg"
    assert headlines.page_image("<title>None</title>", "https://news.example/") is None


def test_shrinks_to_a_webp_lead_and_square_thumbnail():
    lead, thumb = headlines.shrink(picture(1600, 900))
    small_lead, small_thumb = headlines.shrink(picture(400, 300, "PNG"))

    with Image.open(io.BytesIO(lead)) as image:
        assert (image.format, image.size) == ("WEBP", (900, 506))
    with Image.open(io.BytesIO(thumb)) as image:
        assert (image.format, image.size) == ("WEBP", (240, 240))
    assert small_lead is None and small_thumb


def test_refuses_what_is_not_an_image():
    with pytest.raises(UnidentifiedImageError):
        headlines.shrink(b"<svg/>")


def test_asks_nu_nl_for_the_larger_picture():
    assert headlines.bigger("https://images.nu.nl/m/abc_sqr256/1426/6/x.jpg") == (
        "https://images.nu.nl/m/abc_wd1280/1426/6/x.jpg")
    assert headlines.bigger("https://i.example/abc_sqr256/x.jpg") == (
        "https://i.example/abc_sqr256/x.jpg")


# --- choosing the three -----------------------------------------------------------------


class Web:
    def __init__(self):
        self.seen: list[str] = []

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.seen.append(request.url.path)
        jpeg = {"content-type": "image/jpeg"}
        match request.url.path:
            case "/big.jpg":
                return httpx.Response(200, content=picture(1200, 800), headers=jpeg)
            case "/small.jpg":
                return httpx.Response(200, content=picture(300, 200), headers=jpeg)
            case "/og-story":
                return httpx.Response(200, text='<meta property="og:image" content="/big.jpg">')
            case "/lan-story":
                return httpx.Response(
                    200, text='<meta property="og:image" content="http://intranet.lan/x.jpg">')
        return httpx.Response(404)


@pytest.fixture
def groups(store):
    news.ensure_tables(store)
    return [news.add_group(store, title) for title in ("Tech", "Nederland", "Self-hosted")]


def add(store, group: str, path: str, minutes_ago: int, image: str | None = None) -> str:
    url = f"https://news.example{path}"
    news.save_articles(store, group, [{
        "url": url, "title": path.strip("/"), "source": "Example",
        "published": NOW - timedelta(minutes=minutes_ago), "image": image,
        "summary": f"About {path}"}], NOW)
    return news.article_id(url)


def collect(store, web: Web, now: datetime = NOW) -> headlines.Headlines:
    return asyncio.run(headlines.collect(store, httpx.MockTransport(web.handler), now))


def test_one_story_per_group_with_the_newest_lead_sized_picture_first(store, groups):
    tech, nl, home = groups
    add(store, tech, "/older-tech", 90, "https://news.example/big.jpg")
    add(store, tech, "/tech", 30, "https://news.example/small.jpg")
    add(store, nl, "/og-story", 60)
    add(store, home, "/hn", 5)

    result = collect(store, Web())

    assert [(h.title, h.group, h.image) for h in result.items] == [
        ("og-story", "Nederland", "lead"), ("hn", "Self-hosted", None), ("tech", "Tech", "thumb")]
    assert result.items[0].summary == "About /og-story"


def test_a_picture_is_fetched_once_even_when_there_is_none(store, groups):
    add(store, groups[0], "/hn", 5)
    web = Web()

    collect(store, web)
    collect(store, web, NOW + timedelta(minutes=5))

    assert web.seen == ["/hn"]


def test_never_fetches_a_picture_from_a_private_address(store, groups):
    aid = add(store, groups[0], "/lan-story", 5)

    result = collect(store, Web())

    assert result.items[0].image is None
    with store.connect() as conn:
        assert conn.execute("SELECT error FROM headline_image WHERE article_id = ?",
                            (aid,)).fetchone()[0] == "Blocked"


def test_a_feed_image_too_small_for_a_lead_tries_the_page(store, groups):
    add(store, groups[0], "/og-story", 5, "https://news.example/small.jpg")

    assert collect(store, Web()).items[0].image == "lead"


def test_pictures_go_when_their_article_does(store, groups):
    add(store, groups[0], "/og-story", 60 * 24 * 8, None)
    collect(store, Web())

    news.prune(store, NOW)

    with store.connect() as conn:
        assert conn.execute("SELECT COUNT(*) FROM headline_image").fetchone()[0] == 0


def test_the_routes_serve_only_stored_pictures(store, groups):
    aid = add(store, groups[0], "/og-story", 5)
    main.app.state.store = store
    client = TestClient(main.app)
    assert client.get("/api/news/headlines").status_code == 503

    store.put_cache(headlines.CACHE_KEY, collect(store, Web()).model_dump(mode="json"))

    assert client.get("/api/news/headlines").json()["items"][0]["id"] == aid
    lead = client.get(f"/api/news/headlines/{aid}/image/lead")
    assert lead.status_code == 200 and lead.headers["content-type"] == "image/webp"
    assert client.get(f"/api/news/headlines/{aid}/image/huge").status_code == 422
    assert client.get("/api/news/headlines/nope/image/thumb").status_code == 404


def test_a_known_article_keeps_its_read_state_and_gains_a_picture(store, groups):
    item = {"url": "https://news.example/a", "title": "A", "source": "Example",
            "published": NOW, "image": None, "summary": None}
    assert news.save_articles(store, groups[0], [item], NOW) == 1
    news.mark_read(store, news.article_id(item["url"]), True, NOW)

    again = news.save_articles(store, groups[0], [item | {"image": "https://i.example/a.jpg"}],
                               NOW + timedelta(minutes=10))

    with store.connect() as conn:
        row = conn.execute("SELECT image, read_at FROM article").fetchone()
    assert again == 0
    assert row["image"] == "https://i.example/a.jpg" and row["read_at"] is not None
