from __future__ import annotations

import asyncio
import base64
import hashlib
import io
import json
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app import main, music_api
from app.sources import music, spotify

CFG = {"music": {"client_id": "client-123", "default_device": "Apple TV",
                 "default_label": "Apple TV Living Room",
                 "redirect_uri": "https://hub.example.ts.net/api/music/callback"}}
COVER = "https://i.scdn.co/image/abc"


def png(colour=(220, 60, 120)) -> bytes:
    out = io.BytesIO()
    Image.new("RGB", (640, 640), colour).save(out, "PNG")
    return out.getvalue()


def track(name="Midnight City"):
    return {"type": "track", "name": name, "duration_ms": 243000,
            "artists": [{"name": "M83"}], "album": {"name": "Hurry Up", "images": [
                {"url": COVER, "width": 640}, {"url": COVER + "-300", "width": 300},
                {"url": COVER + "-64", "width": 64}]}}


def device(name, active=False, did=None):
    return {"id": did or name.lower().replace(" ", "-"), "name": name, "type": "Smartphone",
            "is_active": active, "volume_percent": 60, "is_restricted": False}


class FakeSpotify:
    def __init__(self):
        self.player = None
        self.devices = [device("iPhone"), device("MacBook Pro")]
        self.recent = []
        self.playlists = [{"id": "p1", "name": "Discover Weekly",
                           "images": [{"url": COVER, "width": 300}],
                           "owner": {"display_name": "Spotify"}},
                          {"id": "p2", "name": "Focus Flow", "images": [], "owner": {}}]
        self.calls: list[tuple[str, str, dict, object]] = []
        self.refresh_refused = False
        self.expired_once = False
        self.tokens = 0

    def handler(self, request: httpx.Request) -> httpx.Response:
        path, host = request.url.path, request.url.host
        if host == "i.scdn.co":
            return httpx.Response(200, content=png(), headers={"content-type": "image/png"})
        if host == "accounts.spotify.com":
            form = parse_qs(request.content.decode())
            self.calls.append(("POST", "token", {k: v[0] for k, v in form.items()}, None))
            if form["grant_type"][0] == "refresh_token" and self.refresh_refused:
                return httpx.Response(400, json={"error": "invalid_grant"})
            self.tokens += 1
            return httpx.Response(200, json={"access_token": f"access-{self.tokens}",
                                             "expires_in": 3600, "refresh_token": "refresh-1"})
        body = json.loads(request.content) if request.content else None
        self.calls.append((request.method, path, dict(request.url.params), body))
        if self.expired_once:
            self.expired_once = False
            return httpx.Response(401, json={"error": {"status": 401}})
        if path == "/v1/me/player" and request.method == "GET":
            return httpx.Response(200, json=self.player) if self.player else httpx.Response(204)
        if path == "/v1/me/player/devices":
            return httpx.Response(200, json={"devices": self.devices})
        if path == "/v1/me/player/recently-played":
            return httpx.Response(200, json={"items": self.recent})
        if path == "/v1/me/playlists":
            return httpx.Response(200, json={"items": self.playlists, "next": None})
        return httpx.Response(204)

    def api_calls(self, path):
        return [c for c in self.calls if c[1] == path]


@pytest.fixture
def cloud(store):
    fake = FakeSpotify()
    spotify.ensure_tables(store)
    spotify.CLIENT.transport = httpx.MockTransport(fake.handler)
    spotify.CLIENT.forget()
    yield fake
    spotify.CLIENT.transport = None
    spotify.CLIENT.forget()
    music.wake = None
    music_api._last.clear()


def connect(store):
    with store.connect() as conn:
        conn.execute("INSERT INTO spotify_auth (id, refresh_token, connected_at) "
                     "VALUES (1, 'r', 0)")


def run(coro):
    return asyncio.run(coro)


# --- signing in ------------------------------------------------------------------------


def test_signing_in_with_pkce_keeps_the_refresh_token(store, cloud):
    url = urlsplit(spotify.login_url(CFG, store, now=1000))
    q = {k: v[0] for k, v in parse_qs(url.query).items()}
    assert (url.netloc, q["client_id"], q["code_challenge_method"]) == (
        "accounts.spotify.com", "client-123", "S256")
    assert "client_secret" not in q and "user-modify-playback-state" in q["scope"]

    run(spotify.CLIENT.finish_login(CFG, store, "the-code", q["state"], now=1010))

    (_, _, form, _), = cloud.calls
    challenge = base64.urlsafe_b64encode(hashlib.sha256(form["code_verifier"].encode())
                                         .digest()).decode().rstrip("=")
    assert challenge == q["code_challenge"] and form["code"] == "the-code"
    assert spotify.connected(store)


def test_a_login_state_works_once_and_expires(store, cloud):
    state = parse_qs(urlsplit(spotify.login_url(CFG, store, now=1000)).query)["state"][0]

    with pytest.raises(spotify.SpotifyError, match="expired"):
        run(spotify.CLIENT.finish_login(CFG, store, "c", state, now=1000 + 601))
    with pytest.raises(spotify.SpotifyError, match="expired"):
        run(spotify.CLIENT.finish_login(CFG, store, "c", state, now=1001))
    assert not spotify.connected(store)


def test_a_revoked_hub_is_disconnected(store, cloud):
    connect(store)
    cloud.refresh_refused = True

    with pytest.raises(spotify.SpotifyError) as refused:
        run(music.state(CFG, store))

    assert refused.value.status == 401 and not spotify.connected(store)


# --- what plays ------------------------------------------------------------------------


def test_nothing_is_asked_before_connecting(store, cloud):
    answer = run(music.state(CFG, store))

    assert (answer["connected"], answer["playing"], cloud.calls) == (False, None, [])


def test_a_playing_track_with_its_cover_and_colour(store, cloud):
    connect(store)
    cloud.player = {"is_playing": True, "progress_ms": 97000, "item": track(),
                    "device": device("iPhone", active=True)}

    answer = run(music.state(CFG, store))

    playing = answer["playing"]
    assert (playing["state"], playing["kind"], playing["title"], playing["subtitle"]) == (
        "playing", "track", "Midnight City", "M83 · Hurry Up")
    assert (playing["progress_ms"], playing["duration_ms"], playing["device"]["name"]) == (
        97000, 243000, "iPhone")
    assert playing["colour"] == "#dc3c78"
    image, _ = run(spotify.cover(store, playing["cover"]))
    with Image.open(io.BytesIO(image)) as picture:
        assert (picture.format, picture.size) == ("WEBP", (300, 300))
    assert cloud.api_calls("/v1/me/player")[0][2] == {"additional_types": "episode"}


def test_an_episode_names_its_show(store, cloud):
    connect(store)
    cloud.player = {"is_playing": False, "progress_ms": 5, "device": None, "item": {
        "type": "episode", "name": "Aflevering 312", "duration_ms": 3480000,
        "show": {"name": "Tweakers Podcast", "images": []}, "images": []}}

    playing = run(music.state(CFG, store))["playing"]

    assert (playing["state"], playing["kind"], playing["subtitle"], playing["cover"]) == (
        "paused", "episode", "Tweakers Podcast", None)


def test_when_nothing_plays_what_played_last(store, cloud):
    connect(store)
    cloud.recent = [{"track": track("Wait")}]

    answer = run(music.state(CFG, store))

    assert answer["playing"] is None and answer["last"]["title"] == "Wait"


def test_answers_are_reused_for_a_moment(store, cloud):
    connect(store)

    run(music.state(CFG, store))
    run(music.state(CFG, store))

    assert len(cloud.api_calls("/v1/me/player")) == 1
    assert len([c for c in cloud.calls if c[1] == "token"]) == 1


def test_an_early_expired_token_is_renewed_once(store, cloud):
    connect(store)
    run(music.state(CFG, store))
    spotify.CLIENT.cache.clear()
    cloud.expired_once = True

    run(music.state(CFG, store))

    assert len([c for c in cloud.calls if c[1] == "token"]) == 2


def test_the_main_colour_skips_black_and_white():
    picture = Image.new("RGB", (100, 100), (0, 0, 0))
    picture.paste((250, 250, 250), (0, 0, 50, 100))
    picture.paste((40, 160, 210), (50, 0, 70, 100))

    colour = spotify.main_colour(picture)
    rgb = [int(colour[i:i + 2], 16) for i in (1, 3, 5)]
    assert all(abs(a - b) <= 4 for a, b in zip(rgb, (40, 160, 210), strict=True)), colour


def test_covers_only_from_spotify(store):
    spotify.ensure_tables(store)
    assert spotify.remember_cover(store, "https://i.scdn.co/image/x")
    assert spotify.remember_cover(store, "https://mosaic.scdn.co/640/x")
    assert spotify.remember_cover(store, "https://evil.example/x.jpg") is None
    assert spotify.remember_cover(store, "http://i.scdn.co/image/x") is None


# --- favourites and where they start ---------------------------------------------------


def favourite(store, cloud):
    connect(store)
    run(music.set_favourites(CFG, store, ["p1", "p2"]))


def plays(cloud):
    return [(c[2], c[3]) for c in cloud.calls if c[1] == "/v1/me/player/play"]


def test_choosing_favourites(store, cloud):
    connect(store)

    chosen = run(music.set_favourites(CFG, store, ["p2", "p1"]))

    assert [(f["position"], f["name"]) for f in chosen] == [
        (0, "Focus Flow"), (1, "Discover Weekly")]
    with pytest.raises(spotify.SpotifyError, match="not in your Spotify library"):
        run(music.set_favourites(CFG, store, ["nope"]))
    with pytest.raises(spotify.SpotifyError, match="up to 4"):
        run(music.set_favourites(CFG, store, ["p1", "p1"]))


def test_a_favourite_starts_where_music_already_plays(store, cloud):
    favourite(store, cloud)
    cloud.player = {"is_playing": True, "item": track(), "device": device("iPhone", True)}
    cloud.devices.append(device("Apple TV"))

    run(music.play_favourite(CFG, store, 0))

    assert plays(cloud) == [({"device_id": "iphone"}, {"context_uri": "spotify:playlist:p1"})]


def test_otherwise_on_the_apple_tv(store, cloud):
    favourite(store, cloud)
    cloud.player = {"is_playing": False, "item": track(), "device": device("iPhone")}
    cloud.devices.append(device("Apple TV", did="atv"))

    run(music.play_favourite(CFG, store, 1))

    assert plays(cloud) == [({"device_id": "atv"}, {"context_uri": "spotify:playlist:p2"})]


def test_an_apple_tv_that_is_not_listed_is_woken_first(store, cloud):
    favourite(store, cloud)
    woken = []

    async def wake(cfg):
        woken.append(True)
        return True

    async def tick(seconds):
        if len(cloud.api_calls("/v1/me/player/devices")) >= 2:
            cloud.devices = [device("Apple TV", did="atv")]

    music.wake = wake
    run(music.play_favourite(CFG, store, 0, sleep=tick))

    assert woken == [True] and plays(cloud)[0][0] == {"device_id": "atv"}


def test_without_a_wake_or_when_it_never_shows_up(store, cloud):
    favourite(store, cloud)

    async def tick(seconds):
        return None

    with pytest.raises(spotify.SpotifyError, match="open Spotify on it first") as no_wake:
        run(music.play_favourite(CFG, store, 0, sleep=tick))

    async def wake(cfg):
        return True

    music.wake = wake
    with pytest.raises(spotify.SpotifyError, match="did not show up") as never:
        run(music.play_favourite(CFG, store, 0, sleep=tick))
    assert (no_wake.value.status, never.value.status) == (409, 504)
    assert plays(cloud) == []


# --- the routes ------------------------------------------------------------------------


@pytest.fixture
def client(store, cloud):
    main.app.state.store = store
    main.app.state.config = CFG
    return TestClient(main.app, headers={"origin": "http://testserver"}, follow_redirects=False)


def test_the_routes(client, store, cloud):
    assert client.get("/api/music").json()["connected"] is False
    started = client.get("/api/music/login")
    assert started.status_code == 302 and "accounts.spotify.com" in started.headers["location"]
    assert client.get("/api/music/callback?error=access_denied").headers["location"] == (
        "/settings?music=cancelled#music")
    assert "failed" in client.get("/api/music/callback?code=c&state=nope").headers["location"]

    connect(store)
    cloud.player = {"is_playing": True, "item": track(), "device": device("iPhone", True)}
    playing = client.get("/api/music").json()["playing"]
    cover = client.get(f"/api/music/covers/{playing['cover']}")
    assert cover.status_code == 200 and cover.headers["content-type"] == "image/webp"
    assert client.get("/api/music/covers/unknown").status_code == 404

    assert client.post("/api/music/control/pause", json={}).status_code == 200
    assert ("PUT", "/v1/me/player/pause") in [(c[0], c[1]) for c in cloud.calls]
    assert client.post("/api/music/control/shuffle", json={}).status_code == 422
    assert client.put("/api/music/volume", json={"percent": 101}).status_code == 422
    assert client.post("/api/music/transfer", json={"device_id": "macbook-pro"}).status_code == 200
    assert client.post("/api/music/disconnect", json={}).json() == {"connected": False}


def test_writes_need_the_same_origin(client):
    foreign = client.post("/api/music/control/pause", json={},
                          headers={"origin": "https://evil.example"})
    assert foreign.status_code == 403


def test_a_failing_spotify_serves_the_last_answer_stale(client, store, cloud):
    connect(store)
    cloud.player = {"is_playing": True, "item": track(), "device": device("iPhone", True)}
    assert client.get("/api/music").json()["stale"] is False

    spotify.CLIENT.cache.clear()
    spotify.CLIENT.transport = httpx.MockTransport(lambda r: httpx.Response(503))
    later = client.get("/api/music").json()

    assert later["stale"] is True and later["playing"]["title"] == "Midnight City"


def test_not_set_up_without_a_client_id(client):
    main.app.state.config = {"music": {"client_id": ""}}
    assert client.get("/api/music").status_code == 503


def test_the_living_room_apple_tv_is_known_by_its_id_once_two_are_listed(store, cloud):
    favourite(store, cloud)
    cloud.devices = [device("Apple TV", did="living")]
    run(music.state(CFG, store))  # only one listed: its id is learnt
    cloud.devices = [device("Apple TV", did="bedroom"), device("Apple TV", did="living")]

    run(music.play_favourite(CFG, store, 0))

    assert plays(cloud)[0][0] == {"device_id": "living"}


def test_two_unknown_apple_tvs_are_not_guessed(store, cloud):
    favourite(store, cloud)
    cloud.devices = [device("Apple TV", did="a"), device("Apple TV", did="b")]

    with pytest.raises(spotify.SpotifyError, match="Apple TV Living Room is not available"):
        run(music.play_favourite(CFG, store, 0))


def test_a_machine_that_just_booted_still_asks_spotify(store, cloud, monkeypatch):
    connect(store)
    cloud.recent = [{"track": track("Wait")}]
    monkeypatch.setattr(spotify.time, "monotonic", lambda: 5.0)  # 5 s after boot

    assert run(music.state(CFG, store))["last"]["title"] == "Wait"
