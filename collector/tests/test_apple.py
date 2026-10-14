from __future__ import annotations

import asyncio
import io
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from fastapi.testclient import TestClient
from PIL import Image

from app import main
from app.sources import apple

NOW = datetime(2026, 10, 14, 20, 0, tzinfo=UTC)
CFG = {"apple": {"rooms": [
    {"name": "Living room", "devices": [
        {"name": "Apple TV Living Room", "address": "10.0.0.1"},
        {"name": "Woonkamer", "address": "10.0.0.2"},
        {"name": "Woonkamer (2)", "address": "10.0.0.3"}]},
    {"name": "Bedroom", "devices": [
        {"name": "Apple TV Bedroom", "address": "10.0.0.4"},
        {"name": "Slaapkamer", "address": "10.0.0.5"}]},
    {"name": "Bathroom", "devices": [{"name": "Badkamer", "address": "10.0.0.6"}]},
]}}
TV, POD, MINI = "AppleTV14,1", "AudioAccessory6,1", "AudioAccessory5,1"
MODELS = {"10.0.0.1": TV, "10.0.0.2": POD, "10.0.0.3": POD,
          "10.0.0.4": TV, "10.0.0.5": MINI, "10.0.0.6": MINI}
SHOW = apple.Reading(state="playing", media="video", title="A show", subtitle="S2 E7",
                     app="Jellyfin")


def png() -> bytes:
    out = io.BytesIO()
    Image.new("RGB", (400, 300), (200, 80, 120)).save(out, "PNG")
    return out.getvalue()


class Fake:
    def __init__(self, down=(), playing=None, art=None):
        self.down, self.playing, self.art = set(down), dict(playing or {}), art
        self.reads: list[str] = []
        self.artworks: list[str] = []

    async def ask(self, address):
        if address in self.down:
            return None
        return apple.Answer(model=MODELS[address], airplay=True,
                            border_router=address != "10.0.0.4", thread_active=True)

    async def read(self, address, credentials):
        self.reads.append(address)
        return self.playing.get(address, apple.Reading(state="idle"))

    async def artwork(self, address, credentials):
        self.artworks.append(address)
        return self.art


def collect(store, probe, now=NOW, cfg=CFG):
    apple.ensure_tables(store)
    return asyncio.run(apple.collect(cfg, store, probe, now))


def test_every_device_with_its_kind_and_thread_role(store):
    result = collect(store, Fake())

    assert [r.name for r in result.rooms] == ["Living room", "Bedroom", "Bathroom"]
    devices = {d.name: d for r in result.rooms for d in r.devices}
    assert [(d.id, d.kind, d.online, d.thread) for d in devices.values()] == [
        ("apple-tv-living-room", "tv", True, True), ("woonkamer", "homepod", True, True),
        ("woonkamer-2", "homepod", True, True), ("apple-tv-bedroom", "tv", True, None),
        ("slaapkamer", "homepod_mini", True, True), ("badkamer", "homepod_mini", True, True)]


def test_only_homepods_and_paired_apple_tvs_are_asked_what_plays(store):
    probe = Fake()
    collect(store, probe)

    assert sorted(probe.reads) == ["10.0.0.2", "10.0.0.3", "10.0.0.5", "10.0.0.6"]

    paired = {"apple": {"rooms": [{"name": "Bedroom", "devices": [
        {"name": "Apple TV Bedroom", "address": "10.0.0.4", "credentials": "secret-creds"}]}]}}
    probe = Fake()
    collect(store, probe, cfg=paired)
    assert probe.reads == ["10.0.0.4"]


def test_a_room_plays_what_its_homepods_report_playing_before_paused(store):
    paused = SHOW.model_copy(update={"state": "paused", "title": "Other"})
    probe = Fake(playing={"10.0.0.2": paused, "10.0.0.3": SHOW})

    living = collect(store, probe).rooms[0]

    assert living.playing.model_dump() == {
        "state": "playing", "media": "video", "title": "A show", "subtitle": "S2 E7",
        "app": "Jellyfin", "device": "woonkamer-2", "artwork": False}


def test_artwork_is_fetched_once_per_item_and_served_small(store):
    probe = Fake(playing={"10.0.0.6": SHOW}, art=png())

    first = collect(store, probe)
    collect(store, probe, NOW + timedelta(minutes=1))
    probe.playing["10.0.0.6"] = SHOW.model_copy(update={"subtitle": "S2 E8"})
    collect(store, probe, NOW + timedelta(minutes=2))

    assert first.rooms[2].playing.artwork is True
    assert probe.artworks == ["10.0.0.6", "10.0.0.6"]
    with Image.open(io.BytesIO(apple.artwork(store, "bathroom"))) as image:
        assert (image.format, image.size) == ("WEBP", (200, 200))


def test_an_item_without_artwork_is_not_asked_again(store):
    probe = Fake(playing={"10.0.0.6": SHOW}, art=None)

    collect(store, probe)
    again = collect(store, probe, NOW + timedelta(minutes=1))

    assert probe.artworks == ["10.0.0.6"] and again.rooms[2].playing.artwork is False


def test_an_offline_device_keeps_its_kind_and_since_when(store):
    store.put_cache(apple.CACHE_KEY, collect(store, Fake()).model_dump(mode="json"))
    first = collect(store, Fake(down={"10.0.0.6"}), NOW + timedelta(minutes=1))
    store.put_cache(apple.CACHE_KEY, first.model_dump(mode="json"))

    later = collect(store, Fake(down={"10.0.0.6"}), NOW + timedelta(minutes=5))
    back = collect(store, Fake(), NOW + timedelta(minutes=6))

    bath = later.rooms[2].devices[0]
    assert (bath.online, bath.kind, bath.thread) == (False, "homepod_mini", True)
    assert bath.offline_since == NOW + timedelta(minutes=1)
    assert back.rooms[2].devices[0].offline_since is None


def test_a_device_that_hangs_counts_as_offline(store, monkeypatch):
    monkeypatch.setattr(apple, "QUERY_TIMEOUT", 0)

    class Hanging(Fake):
        async def ask(self, address):
            await asyncio.sleep(5)

    result = collect(store, Hanging())

    assert not any(d.online for r in result.rooms for d in r.devices)


def test_reads_the_kind_and_the_thread_state():
    assert [apple.kind_of(m) for m in ("AppleTV14,1", "AudioAccessory5,1", "AudioAccessory6,1",
                                       "AudioAccessory1,1", "Mac16,12", None)] == [
        "tv", "homepod_mini", "homepod", "homepod", None, None]
    # pyatv hands the binary `sb` value over as text.
    assert apple.thread_active("b'\\x00\\x00\\x0c\\xb1'") is True
    assert apple.thread_active(b"\x00\x00\x00\x09") is False  # initialised, not active
    assert apple.thread_active(None) is False


def test_subtitles_for_episodes_and_music():
    episode = SimpleNamespace(title="Severance", series_name="Severance", season_number=2,
                              episode_number=7, artist=None, album=None)
    music = SimpleNamespace(title="Nightcall", series_name=None, season_number=None,
                            episode_number=None, artist="Kavinsky", album="OutRun")

    assert apple.subtitle_of(episode) == "S2 E7"
    assert apple.subtitle_of(music) == "Kavinsky · OutRun"


def test_switched_off_without_rooms():
    assert apple.settings(CFG)["enabled"] is True
    assert apple.settings({})["enabled"] is False


def test_the_routes(store):
    main.app.state.store = store
    client = TestClient(main.app)
    assert client.get("/api/apple").status_code == 503

    store.put_cache(apple.CACHE_KEY, collect(store, Fake(playing={"10.0.0.6": SHOW}),
                                             ).model_dump(mode="json"))
    assert client.get("/api/apple").json()["rooms"][2]["playing"]["title"] == "A show"
    assert client.get("/api/apple/artwork/bathroom").status_code == 404
    # Addresses stay in config.yaml; the answer has names and ids only.
    assert "10.0.0." not in client.get("/api/apple").text
