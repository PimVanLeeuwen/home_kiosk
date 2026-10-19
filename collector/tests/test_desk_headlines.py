from __future__ import annotations

import io
from datetime import UTC, datetime

from fastapi.testclient import TestClient
from PIL import Image

from app import desk_headlines, main
from app.news import store as news_store

NOW = datetime(2026, 10, 19, 20, 40, tzinfo=UTC)
LEAD_ID, OTHER_ID, BARE_ID = "184bcca116d8c9c8", "6fd9d6a2db4d82fd", "0123456789abcdef"


def item(id_, title, source, published, image):
    return {"id": id_, "group_id": "g", "group": "G", "title": title, "source": source,
            "url": "https://example.com", "published": published, "summary": "", "image": image}


def webp(size, colour=(200, 120, 60)) -> bytes:
    out = io.BytesIO()
    Image.new("RGB", size, colour).save(out, "WEBP")
    return out.getvalue()


def put(store):
    news_store.ensure_tables(store)
    desk_headlines.ensure_tables(store)
    store.put_cache("headlines", {"as_of": NOW.isoformat(), "stale": False, "items": [
        item(LEAD_ID, "Botten van uitgestorven jak \u2013 gevonden", "NU.nl",
             "2026-10-19T20:10:00Z", "lead"),
        item(OTHER_ID, "Japan launches probe", "Bloomberg", "2026-10-19T17:05:00Z", "thumb"),
        item(BARE_ID, "Old news", "NOS", "2026-10-17T08:00:00Z", None)]})
    with store.connect() as conn:
        for id_, lead, thumb in ((LEAD_ID, webp((900, 600)), webp((240, 240))),
                                 (OTHER_ID, None, webp((240, 240)))):
            conn.execute("INSERT INTO headline_image (article_id, checked_at, lead, thumb, error)"
                         " VALUES (?, ?, ?, ?, NULL)", (id_, NOW.isoformat(), lead, thumb))


def test_hidden_without_headlines(store):
    assert desk_headlines.headlines_screen(store, NOW) == {
        "kind": "headlines", "stale": False, "present": False}


def test_three_stories_worded_for_the_panel(store):
    put(store)
    s = desk_headlines.headlines_screen(store, NOW)
    lead, other, bare = s["stories"]
    assert s["present"] and lead["title"] == "Botten van uitgestorven jak - gevonden"
    assert [x["age"] for x in s["stories"]] == ["30 min", "3 h", "2 d"]
    assert lead["picture"] == f"/api/desk/picture/{LEAD_ID}/lead"
    assert other["picture"] == f"/api/desk/picture/{OTHER_ID}/thumb"
    assert bare["picture"] is None
    assert not any(x["saved"] for x in s["stories"])


def test_pictures_are_small_baseline_jpegs_of_the_stored_copies(store):
    put(store)
    main.app.state.store = store
    client = TestClient(main.app)

    lead = client.get(f"/api/desk/picture/{LEAD_ID}/lead")
    assert lead.status_code == 200 and lead.headers["content-type"] == "image/jpeg"
    with Image.open(io.BytesIO(lead.content)) as image:
        assert image.format == "JPEG" and image.size == (640, 320)
        assert not image.info.get("progressive")
    with Image.open(io.BytesIO(client.get(f"/api/desk/picture/{OTHER_ID}/thumb").content)) as image:
        assert image.size == (112, 112)

    assert client.get(f"/api/desk/picture/{OTHER_ID}/lead").status_code == 404
    assert client.get(f"/api/desk/picture/{BARE_ID}/thumb").status_code == 404
    assert client.get("/api/desk/picture/../etc/lead").status_code == 404
    assert client.get(f"/api/desk/picture/{LEAD_ID}/huge").status_code == 422
