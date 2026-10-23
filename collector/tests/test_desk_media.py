from __future__ import annotations

import io
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from fastapi.testclient import TestClient
from PIL import Image

from app import desk_media, main
from app.sources import media_status

ZONE = ZoneInfo("Europe/Amsterdam")
NOW = datetime(2026, 10, 22, 18, 0, tzinfo=UTC)  # Thursday 20:00 in Amsterdam


def download(title, state="downloading", pct=72.4, left=380, poster="sonarr/12"):
    return {"id": f"sonarr:{title}", "kind": "tv", "title": title, "detail": "S2 E5 · 1.4 GB",
            "size_bytes": 1, "left_bytes": 0, "progress_pct": pct, "time_left_seconds": left,
            "client": "qbit", "state": state, "poster": poster}


def episode(series, season=3, number=2, air="2026-10-20T20:00:00+00:00"):
    return {"series": series, "season": season, "episode": number, "title": "x",
            "air_date": air, "poster": None}


def screen(store, downloads=(), missing=(), upcoming=(), total=None):
    store.put_cache(media_status.CACHE_KEY, {
        "as_of": NOW.isoformat(), "stale": False, "downloads": list(downloads),
        "missing": list(missing), "missing_total": len(missing) if total is None else total,
        "upcoming": list(upcoming),
        "posters": {"sonarr/12": "/api/v3/mediacover/12/poster-250.jpg"}})
    return desk_media.media_screen(store, ZONE, NOW)


def test_downloads_with_their_posters_missing_episodes_and_the_next_to_air(store):
    s = screen(store, [download("Harbour Lights"), download("Glass Harbour", pct=31, left=4800,
                                                           poster=None)],
               [episode("Northbound"), episode("The Long Coast", 1, 5,
                                               "2026-10-21T20:00:00+00:00")],
               [episode("The Long Coast", 1, 6, "2026-10-24T20:00:00+00:00")], total=3)
    assert (s["kind"], s["present"], s["status"], s["tone"]) == (
        "media", True, "2 DOWNLOADING", "busy")
    assert s["downloads"][0] == {"title": "Harbour Lights", "detail": "S2 E5 · 1.4 GB",
                                 "progress": 724, "pct": "72%", "left": "6 min",
                                 "state": "downloading", "poster": "/api/desk/poster/sonarr/12"}
    assert (s["downloads"][1]["left"], s["downloads"][1]["poster"]) == ("1 h 20 min", None)
    assert s["missing_title"] == "MISSING · 3 EPISODES"
    assert s["missing"] == [
        {"title": "Northbound", "episode": "S3 E2", "line": "aired 2 days ago"},
        {"title": "The Long Coast", "episode": "S1 E5", "line": "aired yesterday"}]
    assert s["next"] == "Next to air: The Long Coast S1 E6, Saturday"
    assert s["week"] == []


def test_a_failing_download_needs_a_look(store):
    s = screen(store, [download("Harbour Lights", state="warning", left=None)])
    assert (s["status"], s["tone"], s["downloads"][0]["left"]) == (
        "1 NEEDS A LOOK", "warn", "Needs a look")


def test_up_to_date_shows_the_week_ahead(store):
    s = screen(store, upcoming=[episode("Northbound", 3, 3, "2026-10-22T21:00:00+00:00"),
                                episode("Coast", 1, 1, "2026-10-23T19:00:00+00:00")])
    assert (s["status"], s["tone"], s["missing_title"]) == ("UP TO DATE", "ok", "")
    assert [w["line"] for w in s["week"]] == ["today", "tomorrow"]


def test_only_missing_episodes(store):
    assert screen(store, missing=[episode("Northbound")])["status"] == "1 MISSING"


def test_nothing_read_yet(store):
    assert desk_media.media_screen(store, ZONE, NOW) == {
        "kind": "media", "stale": False, "present": False}


def test_posters_are_small_baseline_jpegs_of_current_ones_only(store, monkeypatch):
    main.app.state.store = store
    main.app.state.config = {"timezone": "Europe/Amsterdam"}
    desk_media._posters.clear()
    big = io.BytesIO()
    Image.new("RGB", (250, 375), (40, 80, 160)).save(big, "JPEG")

    async def fake(cfg, store, source, item_id, transport=None):
        if (source, item_id) != ("sonarr", 12):
            raise LookupError(f"{source}/{item_id}")
        return big.getvalue(), "image/jpeg"

    monkeypatch.setattr(media_status, "poster", fake)
    client = TestClient(main.app)
    answer = client.get("/api/desk/poster/sonarr/12")
    assert answer.status_code == 200 and answer.headers["content-type"] == "image/jpeg"
    with Image.open(io.BytesIO(answer.content)) as image:
        assert image.size == desk_media.POSTER and not image.info.get("progressive")
    assert client.get("/api/desk/poster/sonarr/13").status_code == 404
    assert client.get("/api/desk/poster/plex/12").status_code == 422
