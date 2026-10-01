from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from fastapi.testclient import TestClient

from app import main
from app.news import store as news
from app.sources import feeds

NOW = datetime(2026, 10, 1, 12, 0, tzinfo=UTC)
CFG = {
    "timezone": "UTC",
    "news": {
        "max_per_group": 3,
        "title_max_chars": 30,
        "groups": [
            {
                "id": "tech",
                "title": "Tech",
                "feeds": [
                    {"url": "https://ars.example/feed", "name": "Ars"},
                    {"url": "https://dead.example/feed", "name": "Dead"},
                ],
            },
            {"id": "nl", "title": "Nederland", "feeds": ["https://nos.example/rss"]},
        ],
    },
}


@pytest.fixture
def news_store(store):
    news.ensure_tables(store)
    return store


def item(url, title="A story", source="Ars", published=NOW):
    return {"url": url, "title": title, "source": source, "published": published}


# --- feeds -----------------------------------------------------------------------------


def test_seed_copies_config_groups_once(news_store):
    assert news.seed(news_store, CFG) is True
    assert news.seed(news_store, CFG) is False

    groups = news.groups(news_store)
    assert [(g.id, g.title, [f.name for f in g.feeds]) for g in groups] == [
        ("tech", "Tech", ["Ars", "Dead"]),
        ("nl", "Nederland", [None]),
    ]
    assert news.as_config(news_store)[0]["feeds"][0] == {
        "url": "https://ars.example/feed",
        "name": "Ars",
        "feed_id": groups[0].feeds[0].id,
    }


def test_groups_and_feeds_can_be_edited(news_store):
    news.seed(news_store, CFG)

    assert news.add_group(news_store, "Self-hosted & Linux") == "self-hosted-linux"
    assert news.add_group(news_store, "Tech") == "tech-2"  # ids stay unique
    assert news.rename_group(news_store, "nl", "Netherlands")
    feed_id = news.add_feed(news_store, "nl", "https://nu.example/rss", "NU")
    assert news.add_feed(news_store, "missing", "https://x.example", None) is None
    assert news.update_feed(news_store, feed_id, "tech", "https://nu.example/rss2", "NU.nl")
    assert news.delete_group(news_store, "tech-2")

    titles = {g.id: (g.title, [f.url for f in g.feeds]) for g in news.groups(news_store)}
    assert titles["nl"] == ("Netherlands", ["https://nos.example/rss"])
    assert "https://nu.example/rss2" in titles["tech"][1]
    assert "tech-2" not in titles


# --- articles ---------------------------------------------------------------------------


def test_articles_keep_their_read_state_when_seen_again(news_store):
    assert news.save_articles(news_store, "tech", [item("https://a")], NOW) == 1
    aid = news.article_id("https://a")
    news.mark_read(news_store, aid, True, NOW)

    assert news.save_articles(news_store, "tech", [item("https://a", title="Changed")], NOW) == 0
    assert news.article(news_store, aid).read is True


def test_listing_filters_by_group_unread_and_search(news_store):
    news.save_articles(
        news_store,
        "tech",
        [
            item("https://1", "Jellyfin 12.1 lands with faster scans", published=NOW),
            item("https://2", "Apple ships macOS 27.0.1", published=NOW - timedelta(hours=1)),
            item("https://3", "100% of 50_000 users", published=NOW - timedelta(hours=2)),
        ],
        NOW,
    )
    news.save_articles(
        news_store,
        "nl",
        [item("https://4", "Kabinet en Jellyfin", "NOS", NOW - timedelta(minutes=30))],
        NOW,
    )
    news.mark_read(news_store, news.article_id("https://2"), True)

    def ids(**kw):
        found, total = news.articles(news_store, **kw)
        return [a.url[-1] for a in found], total

    assert ids() == (["1", "4", "2", "3"], 4)
    assert ids(group="tech") == (["1", "2", "3"], 3)
    assert ids(unread=True) == (["1", "4", "3"], 3)
    assert ids(q="jellyfin") == (["1", "4"], 2)
    assert ids(q="jellyfin scans") == (["1"], 1)  # every word must match
    assert ids(q="nos") == (["4"], 1)  # source counts too
    assert ids(q="100%") == (["3"], 1)  # LIKE wildcards are literal
    assert ids(q="50_") == (["3"], 1)
    assert ids(limit=2, offset=1) == (["4", "2"], 4)
    assert news.unread_counts(news_store) == {"tech": 2, "nl": 1}

    assert news.mark_all_read(news_store, "tech") == 2
    assert news.unread_counts(news_store) == {"nl": 1}


def test_articles_older_than_a_week_are_pruned(news_store):
    news.save_articles(
        news_store,
        "tech",
        [
            item("https://old", published=NOW - timedelta(days=8)),
            item("https://new", published=NOW - timedelta(days=6)),
        ],
        NOW,
    )

    assert news.prune(news_store, NOW) == 1
    assert [a.url for a in news.articles(news_store)[0]] == ["https://new"]


# --- the feed job ---------------------------------------------------------------------------

RSS = """<?xml version="1.0"?><rss version="2.0"><channel><title>Ars</title>
<item><title>A very long headline that the kiosk has to cut short somewhere</title>
<link>https://ars.example/1</link><pubDate>Wed, 01 Oct 2026 11:00:00 GMT</pubDate></item>
</channel></rss>"""


def test_the_feed_job_stores_full_titles_and_records_feed_health(news_store):
    news.seed(news_store, CFG)

    def handler(request):
        if "dead" in request.url.host:
            return httpx.Response(500)
        if "nos" in request.url.host:
            return httpx.Response(200, text="<html>not a feed</html>")
        return httpx.Response(200, text=RSS)

    kiosk = asyncio.run(feeds.collect(CFG, news_store, transport=httpx.MockTransport(handler)))

    # The kiosk keeps its short titles; the article store has the whole one.
    assert kiosk.groups[0].items[0].title.endswith("…")
    (stored,) = news.articles(news_store, group="tech")[0]
    assert stored.title == "A very long headline that the kiosk has to cut short somewhere"
    health = {f.url: (f.item_count, f.error) for g in news.groups(news_store) for f in g.feeds}
    assert health == {
        "https://ars.example/feed": (1, None),
        "https://dead.example/feed": (0, "HTTP 500"),
        "https://nos.example/rss": (0, "No items: not a feed?"),
    }


# --- endpoints ----------------------------------------------------------------------------


@pytest.fixture
def client(news_store):
    news.seed(news_store, CFG)
    main.app.state.store = news_store
    return TestClient(main.app, headers={"origin": "http://testserver"})


def test_reading_endpoints(client, news_store):
    news.save_articles(news_store, "tech", [item("https://1"), item("https://2")], NOW)
    aid = news.article_id("https://1")

    assert client.get("/api/news/groups").json() == [
        {"id": "tech", "title": "Tech", "unread": 2},
        {"id": "nl", "title": "Nederland", "unread": 0},
    ]
    body = client.get("/api/news/articles", params={"group": "tech", "limit": 1}).json()
    assert (len(body["articles"]), body["total"]) == (1, 2)

    assert client.post(f"/api/news/articles/{aid}/read", json={"read": True}).json() == {
        "read": True
    }
    assert client.get("/api/news/articles", params={"unread": True}).json()["total"] == 1
    assert client.post("/api/news/articles/nope/read", json={"read": True}).status_code == 404
    assert client.post("/api/news/read-all", json={"group": "tech"}).json() == {"marked": 1}


def test_feed_editing_endpoints_validate(client):
    added = client.post(
        "/api/settings/feeds",
        json={"group_id": "nl", "url": " https://nu.example/rss ", "name": " NU "},
    )
    assert added.status_code == 201
    nl = next(g for g in added.json() if g["id"] == "nl")
    assert [(f["url"], f["name"]) for f in nl["feeds"]][-1] == ("https://nu.example/rss", "NU")

    for bad in [{"url": "javascript:alert(1)"}, {"url": "ftp://x"}, {"url": "nope"}]:
        resp = client.post("/api/settings/feeds", json={"group_id": "nl", **bad})
        assert resp.status_code == 422
    assert (
        client.post(
            "/api/settings/feeds", json={"group_id": "missing", "url": "https://x.example"}
        ).status_code
        == 404
    )
    assert client.post("/api/settings/feed-groups", json={"title": "  "}).status_code == 422
    assert client.post("/api/settings/feed-groups", json={"title": "Apple"}).status_code == 201
    assert client.delete("/api/settings/feed-groups/apple").status_code == 200
    assert (
        client.post(
            "/api/settings/feed-groups",
            json={"title": "X"},
            headers={"origin": "https://evil.example"},
        ).status_code
        == 403
    )
