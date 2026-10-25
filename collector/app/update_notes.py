"""Update notes (plan.md M26, step 2): what changed in each image Watchtower updated.

When Watchtower's report arrives, the hub works out per updated container the
version it was and is (the image's OCI labels, kept per image ID by
container_stats, as Watchtower removes the old image) and its GitHub repo (the
`source` label). It reads that repo's releases from the old version to the new
one (public data, at most MAX_RELEASES) and asks Haiku for a note of two short
sentences at most. The report waits for the notes, never longer than
NOTES_TIMEOUT, and goes out once (formats.watchtower).

Only release notes go to Claude: no house state, no names beyond the
container's. An image without a version label, a GitHub source or a matching
release gets its versions line and no note.
"""

from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx

from . import ai
from .sources import container_stats, docker
from .store import Store

log = logging.getLogger(__name__)

FEATURE = "update_notes"
NOTES_TIMEOUT = 180  # seconds the report waits at most
MAX_RELEASES = 5
RELEASE_CHARS = 3000
NOTES_CHARS = 12000
UPDATE_WINDOW = timedelta(hours=12)

SYSTEM = (
    "You write a note for the owner of a home server about a container image that was just "
    "updated, from the project's release notes. At most two short sentences, plain text: what "
    "changed that matters to someone who self-hosts it, and whether anything needs doing (a "
    "breaking change, a config or database migration, a removed feature). When nothing needs "
    "doing, end with \"Nothing to do.\" No markdown, no emoji, no links, and do not repeat the "
    "version numbers."
)

_GITHUB = re.compile(r"github\.com[/:]([\w.-]+)/([\w.-]+?)(?:\.git)?/?$")


@dataclass(frozen=True)
class Change:
    name: str
    image: str
    old: str | None
    new: str | None
    repo: str | None  # owner/name on GitHub

    @property
    def versions(self) -> str | None:
        if self.old and self.new and self.old != self.new:
            return f"{self.old} → {self.new}"
        return self.new


def enabled(cfg: dict[str, Any], store: Store) -> bool:
    return ai.settings(cfg)["enabled"] and ai.switches(store).get(FEATURE, False)


def github_repo(source: str | None) -> str | None:
    match = _GITHUB.search((source or "").strip())
    return f"{match.group(1)}/{match.group(2)}" if match else None


def _norm(version: str) -> str:
    return version.strip().lower().removeprefix("v")


async def changes(cfg: dict[str, Any], store: Store, names: list[str], now: datetime,
                  docker_transport: httpx.AsyncBaseTransport | None = None) -> list[Change]:
    """The updated containers with their versions, noting the update first in case
    the minute's Docker check has not seen it yet."""
    containers = await docker.list_containers(cfg["nas"]["docker_socket"],
                                              transport=docker_transport)
    if containers:
        container_stats.note_updates(store, containers, now)
    labels: dict[str, list[str | None]] = store.get_cache(container_stats.LABELS_KEY) or {}
    recent = [r for r in store.container_updates(200)
              if datetime.fromisoformat(r["ts"]) >= now - UPDATE_WINDOW]
    found = []
    for name in names:
        row = next((r for r in recent if r["name"] == name), None)
        if row is None:
            found.append(Change(name, "", None, None, None))
            continue
        old_version, old_source = labels.get(row["old_image_id"]) or [None, None]
        new_version, new_source = labels.get(row["new_image_id"]) or [None, None]
        found.append(Change(name, row["image"], old_version, new_version,
                            github_repo(new_source or old_source)))
    return found


async def release_notes(client: httpx.AsyncClient, change: Change,
                        token: str = "") -> str | None:
    """The releases after the old version up to the new one, newest first."""
    if not change.repo or not change.new:
        return None
    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    resp = await client.get(f"https://api.github.com/repos/{change.repo}/releases",
                            params={"per_page": 30}, headers=headers)
    resp.raise_for_status()
    # Betas and develop builds sit among the tags; only the image's own version may be one.
    releases = [r for r in resp.json() if isinstance(r, dict) and not r.get("draft")
                and (not r.get("prerelease")
                     or _norm(str(r.get("tag_name") or "")) == _norm(change.new))]
    tags = [_norm(str(r.get("tag_name") or "")) for r in releases]
    if _norm(change.new) not in tags:
        return None
    start = tags.index(_norm(change.new))
    end = start + 1
    if change.old and _norm(change.old) in tags[start + 1:]:
        end = tags.index(_norm(change.old), start + 1)
    picked = releases[start:min(end, start + MAX_RELEASES)]
    text = "\n\n".join(f"## {r.get('tag_name')}\n{(r.get('body') or '').strip()[:RELEASE_CHARS]}"
                       for r in picked)
    return text[:NOTES_CHARS] or None


async def note(cfg: dict[str, Any], store: Store, change: Change, client: httpx.AsyncClient,
               now: datetime, claude: ai.ClientFactory | None = None) -> str | None:
    try:
        notes = await release_notes(client, change, (cfg.get("github") or {}).get("token") or "")
    except httpx.HTTPError as exc:
        log.warning("release notes for %s failed: %s", change.name, type(exc).__name__)
        return None
    if not notes:
        return None
    prompt = (f"Container: {change.name}\nImage: {change.image}\n"
              f"Updated from {change.old or 'an unknown version'} to {change.new}\n\n"
              f"Release notes:\n{notes}")
    return await ai.ask(cfg, store, feature=FEATURE, model=ai.SCHEDULED_MODEL, system=SYSTEM,
                        prompt=prompt, max_tokens=1024, now=now, client=claude)


async def extras(cfg: dict[str, Any], store: Store, names: list[str],
                 now: datetime | None = None,
                 docker_transport: httpx.AsyncBaseTransport | None = None,
                 github_transport: httpx.AsyncBaseTransport | None = None,
                 claude: ai.ClientFactory | None = None) -> dict[str, dict[str, str | None]]:
    """Per container name its versions line and note, for the report's lines;
    whatever is ready when NOTES_TIMEOUT runs out. The transports and `claude`
    are for tests."""
    now = now or datetime.now(UTC)
    found: dict[str, dict[str, str | None]] = {}

    async def work() -> None:
        updated = await changes(cfg, store, names, now, docker_transport)
        for change in updated:
            found[change.name] = {"versions": change.versions, "note": None}
        async with httpx.AsyncClient(timeout=15, transport=github_transport) as client:
            for change in updated:
                found[change.name]["note"] = await note(cfg, store, change, client, now, claude)

    try:
        await asyncio.wait_for(work(), NOTES_TIMEOUT)
    except TimeoutError:
        log.warning("update notes ran out of time; sending what is ready")
    return found
