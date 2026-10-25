from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import httpx
import pytest
from fastapi.testclient import TestClient

from app import ai, main, update_notes
from app.alerts import core
from app.alerts.telegram import Telegram
from app.sources import container_stats, docker

KEY = "notify-key"
CFG = {
    "timezone": "Europe/Amsterdam",
    "nas": {"docker_socket": "/var/run/docker.sock"},
    "ai": {"api_key": "sk-test"},
    "github": {"token": "gh-token"},
    "telegram": {"token": "t", "notify_key": KEY, "chats": {"nas": {"id": "-1", "label": "NAS"}}},
}
NOW = datetime(2026, 10, 25, 2, 5, tzinfo=UTC)
SONARR = "lscr.io/linuxserver/sonarr:latest"
OLD, NEW = "sha256:old", "sha256:new"


def container(image_id, version, source="https://github.com/linuxserver/docker-sonarr"):
    return {"Names": ["/sonarr"], "State": "running", "Status": "Up 1 minute", "Id": "c1",
            "Image": SONARR, "ImageID": image_id,
            "Labels": {"org.opencontainers.image.version": version,
                       "org.opencontainers.image.source": source}}


def docker_answer(*entries):
    return httpx.MockTransport(lambda _: httpx.Response(200, json=list(entries)))


RELEASES = [
    {"tag_name": "4.0.11.2600-ls257", "body": "Not yet ours.", "draft": False},
    {"tag_name": "4.0.10.2544-ls256", "body": "Fixes imports from some indexers.", "draft": False},
    {"tag_name": "develop-5.0.0.2742-ls201", "body": "A develop build.", "prerelease": True},
    {"tag_name": "4.0.9.2400-ls255b", "body": "Faster calendar.", "draft": False},
    {"tag_name": "4.0.9.2244-ls255", "body": "The one we had.", "draft": False},
    {"tag_name": "4.0.8.2000-ls250", "body": "Older.", "draft": False},
]


def github(releases=RELEASES, seen=None):
    def handler(request):
        if seen is not None:
            seen.append(request)
        return httpx.Response(200, json=releases)

    return httpx.MockTransport(handler)


class FakeClaude:
    def __init__(self, text="Fixes indexer imports and speeds up the calendar. Nothing to do.",
                 delay=0.0):
        self.prompts: list[str] = []
        self.text, self.delay = text, delay

    def __call__(self, api_key):
        return SimpleNamespace(messages=SimpleNamespace(create=self.create))

    async def create(self, **kwargs):
        await asyncio.sleep(self.delay)
        self.prompts.append(kwargs["messages"][0]["content"])
        usage = SimpleNamespace(input_tokens=900, output_tokens=60,
                                cache_read_input_tokens=0, cache_creation_input_tokens=0)
        return SimpleNamespace(stop_reason="end_turn", usage=usage,
                               content=[SimpleNamespace(type="text", text=self.text)])


@pytest.fixture
def notes_on(store):
    ai.ensure_tables(store)
    core.ensure_tables(store)
    ai.set_switches(store, {"update_notes": True})
    return store


def seen_before_update(store):
    """The minute's Docker check saw sonarr on its old image before Watchtower ran."""
    before = docker.parse([container(OLD, "4.0.9.2244-ls255")])
    container_stats.note_updates(store, before, NOW - timedelta(hours=1))


def test_reads_the_version_and_source_labels():
    (c,) = docker.parse([container(NEW, "4.0.10.2544-ls256")])

    assert (c.version, c.source) == ("4.0.10.2544-ls256", "https://github.com/linuxserver/docker-sonarr")


def test_github_repo_from_the_source_label():
    assert update_notes.github_repo("https://github.com/immich-app/immich") == "immich-app/immich"
    assert update_notes.github_repo("https://github.com/linuxserver/docker-sonarr.git") == \
        "linuxserver/docker-sonarr"
    assert update_notes.github_repo("https://codeberg.org/readeck/readeck") is None
    assert update_notes.github_repo(None) is None


def test_finds_the_version_before_and_after_even_with_the_old_image_removed(notes_on):
    seen_before_update(notes_on)

    (change,) = asyncio.run(update_notes.changes(
        CFG, notes_on, ["sonarr"], NOW, docker_answer(container(NEW, "4.0.10.2544-ls256"))))

    assert change.old == "4.0.9.2244-ls255" and change.new == "4.0.10.2544-ls256"
    assert change.repo == "linuxserver/docker-sonarr"
    assert change.versions == "4.0.9.2244-ls255 → 4.0.10.2544-ls256"


def test_release_notes_run_from_after_the_old_version_to_the_new_one():
    change = update_notes.Change("sonarr", SONARR, "4.0.9.2244-ls255", "4.0.10.2544-ls256",
                                 "linuxserver/docker-sonarr")
    seen: list[httpx.Request] = []

    async def read(c, token=""):
        async with httpx.AsyncClient(transport=github(seen=seen)) as client:
            return await update_notes.release_notes(client, c, token)

    notes = asyncio.run(read(change, "gh-token"))
    assert notes == ("## 4.0.10.2544-ls256\nFixes imports from some indexers.\n\n"
                     "## 4.0.9.2400-ls255b\nFaster calendar.")
    assert seen[0].url.path == "/repos/linuxserver/docker-sonarr/releases"
    assert seen[0].headers["Authorization"] == "Bearer gh-token"

    unknown_old = update_notes.Change("sonarr", SONARR, None, "v4.0.10.2544-ls256", "x/y")
    assert asyncio.run(read(unknown_old)) == \
        "## 4.0.10.2544-ls256\nFixes imports from some indexers."
    no_release = update_notes.Change("sonarr", SONARR, None, "9.9", "x/y")
    assert asyncio.run(read(no_release)) is None


def extras(store, claude, docker_entries=None, releases=RELEASES):
    return asyncio.run(update_notes.extras(
        CFG, store, ["sonarr"], NOW,
        docker_transport=docker_answer(*(docker_entries or [container(NEW, "4.0.10.2544-ls256")])),
        github_transport=github(releases), claude=claude))


def test_asks_haiku_with_only_the_release_notes_and_versions(notes_on):
    seen_before_update(notes_on)
    claude = FakeClaude()

    found = extras(notes_on, claude)

    assert found == {"sonarr": {
        "versions": "4.0.9.2244-ls255 → 4.0.10.2544-ls256",
        "note": "Fixes indexer imports and speeds up the calendar. Nothing to do."}}
    (prompt,) = claude.prompts
    assert "Updated from 4.0.9.2244-ls255 to 4.0.10.2544-ls256" in prompt
    assert "Fixes imports from some indexers." in prompt and "Not yet ours." not in prompt


def test_with_the_feature_off_there_are_versions_but_no_note(notes_on):
    seen_before_update(notes_on)
    ai.set_switches(notes_on, {"update_notes": False})
    claude = FakeClaude()

    assert extras(notes_on, claude)["sonarr"]["note"] is None
    assert claude.prompts == []


def test_the_report_never_waits_longer_than_the_limit(notes_on, monkeypatch):
    seen_before_update(notes_on)
    monkeypatch.setattr(update_notes, "NOTES_TIMEOUT", 0.2)

    found = extras(notes_on, FakeClaude(delay=5))

    assert found == {"sonarr": {"versions": "4.0.9.2244-ls255 → 4.0.10.2544-ls256", "note": None}}


REPORT = ("🔄 Watchtower: 36 scanned, 1 updated, 0 failed\n"
          "✅ sonarr (lscr.io/linuxserver/sonarr:latest)")


@pytest.fixture
def client(notes_on, monkeypatch):
    sent: list[str] = []

    def handler(request):
        sent.append(json.loads(request.content)["text"])
        return httpx.Response(200, json={"ok": True, "result": {}})

    fake = httpx.MockTransport(handler)
    monkeypatch.setattr(core, "Telegram", lambda token: Telegram(token, transport=fake))
    # Daytime, so quiet hours do not hold the report.
    monkeypatch.setattr(core, "in_quiet_hours", lambda *_: False)
    main.app.state.store = notes_on
    main.app.state.config = CFG
    seen_before_update(notes_on)
    main.app.state.update_notes_test = {
        "now": NOW,
        "docker_transport": docker_answer(container(NEW, "4.0.10.2544-ls256")),
        "github_transport": github(), "claude": FakeClaude()}
    test_client = TestClient(main.app)
    test_client.sent = sent
    yield test_client
    main.app.state.update_notes_test = {}


def post_report(client):
    return client.post("/api/notify", headers={"X-Notify-Key": KEY}, json={
        "title": "", "body": REPORT, "source": "watchtower", "category": "updates",
        "severity": "info"})


def test_the_report_waits_for_its_notes_and_goes_out_once(client):
    resp = post_report(client)

    assert resp.json() == {"queued": True, "notes_for": ["sonarr"]}
    assert client.sent == [
        "<b>INFO</b> · <b>Watchtower: 36 scanned, 1 updated, 0 failed</b>\n"
        "Updated sonarr (lscr.io/linuxserver/sonarr:latest)\n"
        "4.0.9.2244-ls255 → 4.0.10.2544-ls256\n"
        "<i>Fixes indexer imports and speeds up the calendar. Nothing to do.</i>"]


def test_without_notes_switched_on_the_report_goes_at_once_as_before(client, notes_on):
    ai.set_switches(notes_on, {"update_notes": False})

    resp = post_report(client)

    assert resp.json()["status"] == "sent"
    assert client.sent == ["<b>INFO</b> · <b>Watchtower: 36 scanned, 1 updated, 0 failed</b>\n"
                           "Updated sonarr (lscr.io/linuxserver/sonarr:latest)"]
