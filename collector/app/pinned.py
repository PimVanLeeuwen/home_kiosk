"""Pinned images (plan.md M26, step 2b): a warning before an update that breaks.

Watchtower leaves an image alone when its tag is an exact version (Immich's
`v3.3.1`, `uptime-kuma:2.2.1`), so nothing says when a newer release needs care.
Once a day the hub takes every running container with such a tag whose image
names its GitHub repo (the OCI `source` label), one per repo (the newest pin),
and reads the releases since. When the newest release is one it has not judged
yet, Haiku reads those releases and answers BREAKING or NONE; a breaking one
sends one Telegram warning. Part of the "Update notes" switch; only public
release notes go to Claude.
"""

from __future__ import annotations

import logging
import re
from datetime import UTC, datetime
from typing import Any

import httpx

from . import ai, update_notes
from .alerts import core, templates
from .models import PinnedImage, PinnedImages
from .sources import docker
from .store import Store

log = logging.getLogger(__name__)

CACHE_KEY = "pinned"
JUDGED = "pinned_judged"  # {repo: newest release tag judged}
CHECK_AT = "09:00"  # local time, once a day
MAX_RELEASES = 8

# An exact version as the whole tag: v3.3.1, 2.2.1, 3.3.1.0 (not 18-alpine or 8).
_EXACT = re.compile(r":v?\d+(?:\.\d+){1,3}$")

SYSTEM = (
    "You read the release notes of a self-hosted app that its owner runs at an older, pinned "
    "version, and judge whether updating to the newest release needs care. Answer with "
    "BREAKING on the first line when any release since the pinned version needs action before "
    "or during the update (a database or config migration, a removed or renamed setting, a "
    "required change to the compose file, a minimum version to pass through first), and then "
    "at most three short sentences on what to do. Otherwise answer NONE on the first line and "
    "nothing else. Plain text, no markdown, no emoji, no links."
)


def pinned_tag(image: str) -> bool:
    return bool(_EXACT.search(image.split("@", 1)[0]))


def _key(version: str) -> tuple[int, ...]:
    return tuple(int(n) for n in re.findall(r"\d+", version))


def pins(containers: list[Any]) -> list[PinnedImage]:
    """One per GitHub repo: the running container on the newest exact pin."""
    best: dict[str, PinnedImage] = {}
    for c in containers:
        repo = update_notes.github_repo(c.source)
        if c.state != "running" or not repo or not pinned_tag(c.image):
            continue
        version = c.version or c.image.rsplit(":", 1)[1]
        if repo not in best or _key(version) > _key(best[repo].current):
            best[repo] = PinnedImage(repo=repo, container=c.name, current=version)
    return sorted(best.values(), key=lambda p: p.repo)


def newer(releases: list[dict[str, Any]], current: str) -> list[dict[str, Any]]:
    """The releases after the pinned version, newest first, without betas."""
    out = []
    for r in releases:
        tag = update_notes.norm(str(r.get("tag_name") or ""))
        if tag == update_notes.norm(current):
            break
        if not r.get("prerelease") and _key(tag) > _key(current):
            out.append(r)
    return out[:MAX_RELEASES]


async def judge(cfg: dict[str, Any], store: Store, pin: PinnedImage,
                releases: list[dict[str, Any]], now: datetime,
                claude: ai.ClientFactory | None) -> tuple[bool | None, str | None]:
    prompt = (f"App: {pin.repo}\nPinned version: {pin.current}\n\n"
              f"Release notes since then:\n{update_notes.as_text(releases)}")
    answer = await ai.ask(cfg, store, feature=update_notes.FEATURE, model=ai.SCHEDULED_MODEL,
                          system=SYSTEM, prompt=prompt, max_tokens=1024, now=now, client=claude)
    if answer is None:
        return None, None
    first, _, rest = answer.strip().partition("\n")
    if first.strip().upper().startswith("BREAKING"):
        return True, rest.strip() or None
    return False, None


async def collect(cfg: dict[str, Any], store: Store, now: datetime | None = None,
                  docker_transport: httpx.AsyncBaseTransport | None = None,
                  github_transport: httpx.AsyncBaseTransport | None = None,
                  claude: ai.ClientFactory | None = None, telegram: Any = None) -> PinnedImages:
    """The transports, `claude` and `telegram` are for tests."""
    now = now or datetime.now(UTC)
    containers = await docker.list_containers(cfg["nas"]["docker_socket"],
                                              transport=docker_transport)
    if containers is None:
        raise RuntimeError("docker socket unavailable")
    judged: dict[str, str] = core.get_setting(store, JUDGED, {})
    token = (cfg.get("github") or {}).get("token") or ""
    found = []
    async with httpx.AsyncClient(timeout=15, transport=github_transport) as client:
        for pin in pins(containers):
            try:
                since = newer(await update_notes.fetch_releases(client, pin.repo, token),
                              pin.current)
            except httpx.HTTPError as exc:
                log.warning("releases of %s failed: %s", pin.repo, type(exc).__name__)
                found.append(pin)
                continue
            if not since:
                found.append(pin)
                continue
            latest = str(since[0].get("tag_name"))
            pin = pin.model_copy(update={"latest": latest, "behind": len(since),
                                         "url": since[0].get("html_url")})
            if judged.get(pin.repo) != latest and update_notes.enabled(cfg, store):
                breaking, note = await judge(cfg, store, pin, since, now, claude)
                if breaking is not None:
                    judged[pin.repo] = latest
                    core.put_setting(store, JUDGED, judged)
                if breaking:
                    sent = templates.message(store, "pinned_breaking", {
                        "app": pin.repo.split("/")[-1], "current": pin.current,
                        "latest": latest, "note": note or "", "url": pin.url or ""})
                    await core.notify(store, cfg, source="pinned", category="updates",
                                      severity="warning", title=sent.title, body=sent.body,
                                      formatted=sent.html, now=now, telegram=telegram)
            found.append(pin)
    return PinnedImages(as_of=now, pins=found)
