from __future__ import annotations

import asyncio
import io
import json
from datetime import UTC, datetime

import httpx
from PIL import Image

from app.sources import photo

CFG = {"timezone": "Europe/Amsterdam",
       "widgets": {"host": "nas.example", "keys": {"immich": "k-test"}}}
NOW = datetime(2026, 10, 26, 5, tzinfo=UTC)


def asset(id_, people=(), make="Apple", mime="image/jpeg", when="2019-10-26T10:00:00Z"):
    return {"id": id_, "type": "IMAGE", "originalMimeType": mime,
            "exifInfo": {"make": make, "dateTimeOriginal": when},
            "people": [{"name": p} for p in people]}


def test_named_people_first_text_like_left_out():
    receipt, beach, family, shot = (asset("receipt"), asset("beach"), asset("family", ["Anna"]),
                                    asset("shot", make=None, mime="image/png"))
    ranks = {"receipt": 0.0, "shot": 0.2, "beach": 0.6, "family": 0.9}
    pick = photo.choose([(a, ranks[a["id"]]) for a in (receipt, beach, family, shot)])
    assert pick["id"] == "family"
    assert photo.choose([(receipt, 0.0), (beach, 0.6)])["id"] == "beach"
    assert photo.choose([(shot, None)]) is None  # a screenshot, whatever its rank


def test_reads_the_memories_ranks_the_day_and_keeps_the_picture(store):
    seen = []
    out = io.BytesIO()
    Image.new("RGB", (60, 40), (200, 120, 40)).save(out, "JPEG")

    def handler(request):
        seen.append((request.method, request.url.path, request.headers.get("x-api-key")))
        if request.url.path == "/api/memories":
            return httpx.Response(200, json=[{"type": "on_this_day", "assets": [
                asset("a1"), asset("a2", ["Anna", "Bob"]), asset("a3"), asset("a4")]}])
        if request.url.path == "/api/search/smart":
            assert "receipt" in json.loads(request.content)["query"]
            return httpx.Response(200, json={"assets": {"items": [
                {"id": "a1"}, {"id": "a3"}, {"id": "a4"}, {"id": "a2"}]}})
        return httpx.Response(200, content=out.getvalue())

    result = asyncio.run(photo.collect(CFG, store, NOW, httpx.MockTransport(handler)))

    assert (result.asset, result.taken, result.years, result.people) == (
        "a2", "2019-10-26", 7, ["Anna", "Bob"])
    assert photo.KEPT.asset == "a2" and photo.KEPT.picture == out.getvalue()
    assert {s[2] for s in seen} == {"k-test"}
    assert seen[-1][1] == "/api/assets/a2/thumbnail"


def test_off_without_a_key():
    assert photo.settings({"widgets": {"keys": {}}})["enabled"] is False
    assert photo.settings(CFG)["url"] == "http://nas.example:2283"


def test_the_hub_serves_the_kept_picture_and_nothing_without_one(store):
    from fastapi.testclient import TestClient

    from app import main
    main.app.state.store = store
    client = TestClient(main.app)
    photo.KEPT.asset, photo.KEPT.picture = None, None
    assert client.get("/api/photo").status_code == 503
    assert client.get("/api/photo/picture").status_code == 404
    out = io.BytesIO()
    Image.new("RGB", (8, 8), (40, 80, 120)).save(out, "WEBP")
    store.put_cache(photo.CACHE_KEY, {"as_of": "x", "stale": False, "asset": "a1",
                                      "taken": "2019-10-26", "years": 7, "people": ["Anna"]})
    photo.KEPT.asset, photo.KEPT.picture = "a1", out.getvalue()
    try:
        assert client.get("/api/photo").json()["people"] == ["Anna"]
        got = client.get("/api/photo/picture")
        assert got.headers["content-type"] == "image/webp" and got.content == out.getvalue()
    finally:
        photo.KEPT.asset, photo.KEPT.picture = None, None
