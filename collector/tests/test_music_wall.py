"""The Home panel's cover wall (plan.md M27, M): the playlists and albums played lately."""

from __future__ import annotations

from app import desk_home, paint_music
from app.sources import music
from tests.test_music import CFG, COVER, cloud, connect, favourite, plays, run, track  # noqa: F401


def played(context=None, album="Hurry Up", album_uri="spotify:album:a1"):
    item = {"track": track() | {"album": track()["album"] | {"name": album, "uri": album_uri}}}
    item["context"] = context
    return item


def playlist(pid):
    return {"type": "playlist", "uri": f"spotify:playlist:{pid}"}


def test_played_lately_is_four_different_playlists_or_albums(store, cloud):  # noqa: F811
    favourite(store, cloud)  # p1 and p2
    music._PLAYLISTS.clear()
    cloud.lookups = {"p9": {"name": "Late Night", "images": [{"url": COVER, "width": 300}]}}
    cloud.recent = [
        played(playlist("p9")), played(playlist("p9")),  # the same playlist twice: once
        played(playlist("p1")),                          # a favourite: left out
        played(playlist("mix")),                         # Spotify's own mix: its album
        played(None, "Low Tide", "spotify:album:a2"),    # liked songs: its album
        played({"type": "artist", "uri": "spotify:artist:x"}, "Undertow", "spotify:album:a3"),
        played(None, "One More", "spotify:album:a4"),
    ]

    state = run(music.state(CFG, store))

    assert [(r["kind"], r["name"]) for r in state["recent"]] == [
        ("playlist", "Late Night"), ("album", "Hurry Up"), ("album", "Low Tide"),
        ("album", "Undertow")]
    assert all(r["cover"] and r["colour"] for r in state["recent"])
    # Each playlist is looked up once, also one Spotify does not show.
    run(music.state(CFG, store))
    assert len(cloud.api_calls("/v1/playlists/p9")) == 1
    assert len(cloud.api_calls("/v1/playlists/mix")) == 1


def test_a_tap_plays_one_from_the_start(store, cloud):  # noqa: F811
    connect(store)
    music._PLAYLISTS.clear()
    cloud.recent = [played(None, "Low Tide", "spotify:album:a2")]
    cloud.player = {"is_playing": True, "item": track(), "device": {
        "id": "iphone", "name": "iPhone", "type": "Smartphone", "is_active": True}}

    run(music.play_recent(CFG, store, 0))

    assert plays(cloud) == [({"device_id": "iphone"}, {"context_uri": "spotify:album:a2"})]
    try:
        run(music.play_recent(CFG, store, 3))
        raise AssertionError("expected a 404")
    except music.SpotifyError as exc:
        assert exc.status == 404


def wall_music(**extra):
    return {"connected": True, "default_device": "Apple TV", "stale": False,
            "favourites": [{"position": 0, "id": "p1", "name": "Hardlopen", "cover": "c1",
                            "colour": "#336699"}],
            "recent": [{"uri": "spotify:album:a2", "kind": "album", "name": "Low Tide",
                        "cover": "c2", "colour": "#aa5533"}],
            "playing": None, "last": None} | extra


def test_the_wall_lights_what_plays_and_says_so():
    playing = {"title": "Low Tide", "subtitle": "", "context": "spotify:album:a2",
               "colour": "#aa5533", "device": None}

    screen = desk_home.music_screen(wall_music(playing=playing))

    assert screen["present"] and screen["colour"] == "#aa5533"
    assert screen["favourites"][0]["wall"] == "/api/desk/cover/c1/wall"
    assert [r["playing"] for r in screen["recent"]] == [True]
    assert not screen["favourites"][0]["playing"]
    assert screen["footer"] == "Low Tide is playing · tap a cover to play it"
    assert paint_music.inputs(screen, None) == {"colour": "#aa5533", "lit": [1, 0]}
    assert paint_music.paint_music({"colour": "#aa5533", "lit": [1, 0]}).size == (720, 720)


def test_the_wall_shows_with_only_played_lately_and_hides_without_either():
    only_recent = desk_home.music_screen(wall_music(favourites=[], last={"title": "Undertow"}))
    assert only_recent["present"] and only_recent["favourites"] == []
    assert only_recent["footer"] == "Last played: Undertow · tap a cover to play it"
    assert not desk_home.music_screen(wall_music(favourites=[], recent=[]))["present"]


def test_the_music_page_plays_one_played_lately(store, cloud):  # noqa: F811
    from fastapi.testclient import TestClient

    from app import main
    main.app.state.store, main.app.state.config = store, CFG
    client = TestClient(main.app, headers={"origin": "http://testserver"})
    connect(store)
    music._PLAYLISTS.clear()
    cloud.recent = [played(None, "Low Tide", "spotify:album:a2")]
    cloud.player = {"is_playing": True, "item": track(), "context": {"uri": "spotify:album:a2"},
                    "device": {"id": "iphone", "name": "iPhone", "type": "Smartphone",
                               "is_active": True}}

    answer = client.get("/api/music").json()
    assert answer["recent"][0]["name"] == "Low Tide"
    assert answer["playing"]["context"] == "spotify:album:a2"
    assert client.post("/api/music/recent/0/play", json={}).json()["ok"] is True
    assert plays(cloud)[-1][1] == {"context_uri": "spotify:album:a2"}
    assert client.post("/api/music/recent/5/play", json={}).status_code == 404
    foreign = client.post("/api/music/recent/0/play", json={},
                          headers={"origin": "https://evil.example"})
    assert foreign.status_code == 403
