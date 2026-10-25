from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from types import SimpleNamespace

import httpx
import pytest

from app import ai, pinned
from app.alerts import core
from app.alerts.telegram import Telegram
from app.sources import docker

CFG = {
    "timezone": "Europe/Amsterdam",
    "nas": {"docker_socket": "/var/run/docker.sock"},
    "ai": {"api_key": "sk-test"},
    "telegram": {"token": "t", "chats": {"nas": {"id": "-1", "label": "NAS"}}},
}
NOW = datetime(2026, 10, 25, 7, 0, tzinfo=UTC)  # 09:00 in Amsterdam
IMMICH = "https://github.com/immich-app/immich"


def entry(name, image, version=None, source=IMMICH, state="running"):
    labels = {"org.opencontainers.image.source": source} if source else {}
    if version:
        labels["org.opencontainers.image.version"] = version
    return {"Names": [f"/{name}"], "State": state, "Status": "Up", "Id": name, "Image": image,
            "ImageID": f"sha256:{name}", "Labels": labels}


CONTAINERS = [
    entry("immich_server", "ghcr.io/immich-app/immich-server:v3.3.1", "v3.3.1"),
    entry("immich_machine_learning", "ghcr.io/immich-app/immich-machine-learning:v3.0.3",
          "v3.0.3"),
    entry("uptime-kuma", "louislam/uptime-kuma:2.2.1", None, "https://github.com/louislam/uptime-kuma"),
    entry("sonarr", "lscr.io/linuxserver/sonarr:latest", "4.0.20.3014-ls1",
          "https://github.com/linuxserver/docker-sonarr"),
    entry("db", "postgres:18-alpine", "18.1", "https://github.com/docker-library/postgres"),
    entry("old", "ghcr.io/x/y:v1.0.0", "v1.0.0", "https://github.com/x/y", state="exited"),
]

IMMICH_RELEASES = [
    {"tag_name": "v3.4.0-rc.1", "body": "A beta.", "prerelease": True},
    {"tag_name": "v3.4.0", "body": "Machine-learning settings move to the admin page.",
     "html_url": "https://github.com/immich-app/immich/releases/tag/v3.4.0"},
    {"tag_name": "v3.3.5", "body": "Fixes."},
    {"tag_name": "v3.3.1", "body": "The one we run."},
    {"tag_name": "v3.3.0", "body": "Older."},
]
KUMA_RELEASES = [{"tag_name": "2.2.1", "body": "Current."}]


def github(seen=None):
    def handler(request):
        if seen is not None:
            seen.append(request.url.path)
        repo = request.url.path.split("/")[3]
        return httpx.Response(200, json=IMMICH_RELEASES if repo == "immich" else KUMA_RELEASES)

    return httpx.MockTransport(handler)


class FakeClaude:
    def __init__(self, answer):
        self.answer, self.prompts = answer, []

    def __call__(self, api_key):
        return SimpleNamespace(messages=SimpleNamespace(create=self.create))

    async def create(self, **kwargs):
        self.prompts.append(kwargs["messages"][0]["content"])
        usage = SimpleNamespace(input_tokens=2000, output_tokens=80,
                                cache_read_input_tokens=0, cache_creation_input_tokens=0)
        return SimpleNamespace(stop_reason="end_turn", usage=usage,
                               content=[SimpleNamespace(type="text", text=self.answer)])


class Sent:
    def __init__(self):
        self.texts = []

    def client(self):
        def handler(request):
            self.texts.append(json.loads(request.content)["text"])
            return httpx.Response(200, json={"ok": True, "result": {}})

        return Telegram("t", transport=httpx.MockTransport(handler))


@pytest.fixture
def notes_on(store):
    ai.ensure_tables(store)
    core.ensure_tables(store)
    ai.set_switches(store, {"update_notes": True})
    return store


def run(store, claude, sent, now=NOW, seen=None):
    return asyncio.run(pinned.collect(
        CFG, store, now, docker_transport=httpx.MockTransport(
            lambda _: httpx.Response(200, json=CONTAINERS)),
        github_transport=github(seen), claude=claude, telegram=sent.client()))


BREAKING = ("BREAKING\nv3.4.0 moves the machine-learning settings into the admin page; "
            "set them again after updating.")


def test_watches_one_running_exact_pin_per_repo():
    found = pinned.pins(docker.parse(CONTAINERS))

    assert [(p.repo, p.container, p.current) for p in found] == [
        ("immich-app/immich", "immich_server", "v3.3.1"),
        ("louislam/uptime-kuma", "uptime-kuma", "2.2.1"),
    ]


def test_an_exact_pin_is_a_full_version_tag():
    assert pinned.pinned_tag("ghcr.io/immich-app/immich-server:v3.3.1")
    assert pinned.pinned_tag("apache/tika:3.3.1.0")
    assert pinned.pinned_tag("louislam/uptime-kuma:2.2.1@sha256:abc")
    assert not pinned.pinned_tag("postgres:18-alpine")
    assert not pinned.pinned_tag("gotenberg/gotenberg:8")
    assert not pinned.pinned_tag("lscr.io/linuxserver/sonarr:latest")


def test_a_breaking_release_sends_one_warning_with_what_to_do(notes_on):
    sent, claude = Sent(), FakeClaude(BREAKING)

    result = run(notes_on, claude, sent)

    immich = result.pins[0]
    assert (immich.latest, immich.behind) == ("v3.4.0", 2)
    (prompt,) = claude.prompts  # Uptime Kuma has nothing newer
    assert "Pinned version: v3.3.1" in prompt
    assert "Machine-learning settings move" in prompt and "A beta." not in prompt
    assert sent.texts == [
        "<b>WARNING</b> · <b>immich: read before updating to v3.4.0</b>\n"
        "You run v3.3.1.\n<i>v3.4.0 moves the machine-learning settings into the admin page; "
        "set them again after updating.</i>\n"
        "https://github.com/immich-app/immich/releases/tag/v3.4.0"]

    run(notes_on, claude, sent)
    assert len(sent.texts) == 1 and len(claude.prompts) == 1


def test_nothing_breaking_is_silent_and_judged_once(notes_on):
    sent, claude = Sent(), FakeClaude("NONE")

    run(notes_on, claude, sent)
    run(notes_on, claude, sent)

    assert sent.texts == [] and len(claude.prompts) == 1
    assert core.get_setting(notes_on, pinned.JUDGED, {}) == {"immich-app/immich": "v3.4.0"}


def test_without_the_switch_it_only_counts_the_releases(notes_on):
    ai.set_switches(notes_on, {"update_notes": False})
    sent, claude = Sent(), FakeClaude(BREAKING)

    result = run(notes_on, claude, sent)

    assert result.pins[0].behind == 2
    assert claude.prompts == [] and sent.texts == []
    assert core.get_setting(notes_on, pinned.JUDGED, {}) == {}
