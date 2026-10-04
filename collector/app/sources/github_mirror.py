"""Nightly git mirror of your and Hubble's GitHub repos, as a backup.

Every repo of the owners marked `mirror: true` in config.yaml (forks left out,
archived ones kept) is kept as a bare `git clone --mirror` in
`<dir>/<owner>/<repo>.git`. The folder is on /volume3, so the 03:00 rclone run
takes it to the Hetzner storage box. It is an exact copy, deliberately: a repo
deleted on GitHub is deleted here too, and a force-push overwrites history here
as well. Only the git history is kept, no issues or pull requests.

The token goes to git as an HTTP header through the environment, never in the
remote URL, so it is not written into the mirrors' config (and so not into the
backup). Towards GitHub this stays read-only.
"""

from __future__ import annotations

import asyncio
import base64
import logging
import os
import re
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

from ..alerts import core as alerts_core
from ..alerts import templates
from ..models import GitHubMirror, MirroredRepo, MirrorOwner, MirrorRun
from ..store import Store
from .backups import next_run
from .github import MAX_PAGES, TIMEOUT_SECONDS, GitHubError, _graphql, describe

log = logging.getLogger(__name__)

CACHE_KEY = "github_mirror"
MAX_RUNS = 30
GIT_TIMEOUT_SECONDS = 1800  # a first clone of a big repo over a slow line
PARTIAL = ".partial"
# GitHub repo names; anything else (a path trick) is never used as a folder.
SAFE_NAME = re.compile(r"^[A-Za-z0-9._-]+$")

LIST_QUERY = """
query($login: String!, $cursor: String) {
  repositoryOwner(login: $login) {
    repositories(first: 100, after: $cursor) {
      pageInfo { hasNextPage endCursor }
      nodes { name nameWithOwner url isFork isArchived }
    }
  }
}
"""


def settings(cfg: dict[str, Any]) -> dict[str, Any]:
    gh = cfg.get("github") or {}
    mirror = gh.get("mirror") or {}
    owners = [o for o in gh.get("owners", []) if o.get("mirror")]
    return {
        "dir": mirror.get("dir", "/backups/github"),
        "at": str(mirror.get("at", "02:00")),
        "owners": owners,
        "token": (gh.get("token") or "").strip(),
        "enabled": bool(owners),
    }


async def list_repos(client: httpx.AsyncClient, token: str, login: str) -> list[dict[str, Any]]:
    """The owner's own repos, forks left out: [{name, url, archived}]."""
    repos: list[dict[str, Any]] = []
    cursor = None
    for _ in range(MAX_PAGES):
        data = await _graphql(client, token, LIST_QUERY, {"login": login, "cursor": cursor})
        owner = data.get("repositoryOwner")
        if owner is None:
            raise GitHubError(f"No GitHub user or organisation called {login}")
        page = owner["repositories"]
        for node in page["nodes"]:
            if not node or node.get("isFork"):
                continue
            # A user's list also holds repos they only collaborate on.
            if node["nameWithOwner"].split("/")[0].lower() != login.lower():
                continue
            if not SAFE_NAME.match(node["name"]) or node["name"] in {".", ".."}:
                log.warning("skipping repo with an unexpected name: %r", node["name"])
                continue
            repos.append({"name": node["name"], "url": node["url"],
                          "archived": bool(node.get("isArchived"))})
        if not page["pageInfo"]["hasNextPage"]:
            return repos
        cursor = page["pageInfo"]["endCursor"]
    # Stopping early would delete the mirrors of every repo not reached.
    raise GitHubError(f"More than {MAX_PAGES * 100} repos for {login}")


def git_env(token: str) -> dict[str, str]:
    basic = base64.b64encode(f"x-access-token:{token}".encode()).decode()
    return os.environ | {
        "GIT_TERMINAL_PROMPT": "0",
        # Config through the environment: not on the command line, not on disk.
        "GIT_CONFIG_COUNT": "1",
        "GIT_CONFIG_KEY_0": "http.https://github.com/.extraHeader",
        "GIT_CONFIG_VALUE_0": f"Authorization: Basic {basic}",
    }


def clone_url(url: str) -> str:
    return url if url.endswith(".git") or not url.startswith("https://") else f"{url}.git"


async def git(args: list[str], env: dict[str, str], timeout: float = GIT_TIMEOUT_SECONDS) -> None:
    proc = await asyncio.create_subprocess_exec(
        "git", *args, env=env,
        stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.PIPE,
    )
    try:
        _, stderr = await asyncio.wait_for(proc.communicate(), timeout)
    except TimeoutError:
        proc.kill()
        await proc.wait()
        raise GitHubError(f"git timed out after {int(timeout // 60)} min") from None
    if proc.returncode != 0:
        lines = [ln.strip() for ln in stderr.decode(errors="replace").splitlines() if ln.strip()]
        reason = (lines[-1] if lines else f"git exited with {proc.returncode}")[:200]
        raise GitHubError(reason)


async def mirror_one(url: str, dest: Path, env: dict[str, str]) -> None:
    """Clone a new mirror or bring an existing one up to date."""
    if dest.is_dir():
        await git(["-C", str(dest), "remote", "set-url", "origin", url], env)
        await git(["-C", str(dest), "fetch", "--prune", "--quiet", "origin"], env)
        return
    partial = dest.with_name(dest.name + PARTIAL)
    shutil.rmtree(partial, ignore_errors=True)
    await git(["clone", "--mirror", "--quiet", url, str(partial)], env)
    partial.rename(dest)


def folder_bytes(path: Path) -> int:
    total = 0
    for root, _, files in os.walk(path):
        for name in files:
            try:
                total += (Path(root) / name).stat().st_size
            except OSError:
                pass
    return total


async def mirror_owner(
    client: httpx.AsyncClient, owner: dict[str, Any], default_token: str, base: Path,
    previous: dict[str, Any] | None, now: datetime,
) -> MirrorOwner:
    login, label = owner["login"], owner.get("label", owner["login"])
    token = (owner.get("token") or "").strip() or default_token
    before = {r["full_name"]: r for r in (previous or {}).get("repos", [])}
    try:
        if not token:
            raise GitHubError("No GitHub token set (GITHUB_TOKEN)")
        listed = await list_repos(client, token, login)
    except Exception as exc:
        log.warning("github mirror: listing %s failed: %s", login, type(exc).__name__)
        # Keep every mirror as it is and show the last known list.
        kept = [MirroredRepo.model_validate(r | {"ok": False, "error": None})
                for r in before.values()]
        return MirrorOwner(login=login, label=label, repos=kept, error=describe(exc))

    folder = base / login
    folder.mkdir(exist_ok=True)
    env = git_env(token)
    repos: list[MirroredRepo] = []
    for item in listed:
        full_name = f"{login}/{item['name']}"
        dest = folder / f"{item['name']}.git"
        last = before.get(full_name, {}).get("mirrored_at")
        try:
            await mirror_one(clone_url(item["url"]), dest, env)
            repos.append(MirroredRepo(full_name=full_name, archived=item["archived"], ok=True,
                                      mirrored_at=now, bytes=folder_bytes(dest)))
        except Exception as exc:
            log.warning("github mirror: %s failed: %s", full_name, type(exc).__name__)
            repos.append(MirroredRepo(
                full_name=full_name, archived=item["archived"], ok=False,
                error=describe(exc), mirrored_at=last,
                bytes=folder_bytes(dest) if dest.is_dir() else None))

    # Gone from GitHub: gone here too. Also clears clones cut off half-way.
    wanted = {f"{item['name']}.git" for item in listed}
    removed = []
    for entry in sorted(folder.iterdir()):
        if entry.name in wanted or not entry.is_dir():
            continue
        if entry.name.endswith(".git"):
            removed.append(f"{login}/{entry.name.removesuffix('.git')}")
        elif not entry.name.endswith(PARTIAL):
            continue
        shutil.rmtree(entry, ignore_errors=True)
    return MirrorOwner(login=login, label=label, repos=repos, removed=removed)


async def collect(
    cfg: dict[str, Any], store: Store, transport: httpx.AsyncBaseTransport | None = None,
    now: datetime | None = None, telegram: Any = None,
) -> GitHubMirror:
    """One mirror run. `transport` and `telegram` are for tests."""
    s = settings(cfg)
    started = now or datetime.now(UTC)
    previous = store.get_cache(CACHE_KEY) or {}
    runs = [MirrorRun.model_validate(r) for r in previous.get("runs", [])]
    last_success = previous.get("last_success")
    tz = cfg.get("timezone", "UTC")
    result = GitHubMirror(as_of=started, enabled=s["enabled"], dir=s["dir"], runs=runs,
                          last_success=last_success)
    if not s["enabled"]:
        return result

    base = Path(s["dir"])
    if not base.is_dir():
        # Never create it: without the mount the mirrors would land inside the
        # container and be lost on the next update, unseen by the backup.
        result.error = f"Mirror folder {base} not found: is /volume3/backups/github mounted?"
        result.owners = [MirrorOwner.model_validate(o) for o in previous.get("owners", [])]
    else:
        before = {o["login"]: o for o in previous.get("owners", [])}
        async with httpx.AsyncClient(
            timeout=TIMEOUT_SECONDS,
            transport=transport,
            headers={"Accept": "application/vnd.github+json",
                     "X-GitHub-Api-Version": "2022-11-28"},
        ) as client:
            result.owners = [
                await mirror_owner(client, owner, s["token"], base, before.get(owner["login"]),
                                   started)
                for owner in s["owners"]
            ]

    finished = datetime.now(UTC) if now is None else started
    repos = [r for o in result.owners for r in o.repos]
    failed = [r for r in repos if not r.ok]
    ok = result.error is None and not failed and not any(o.error for o in result.owners)
    result.runs = [MirrorRun(
        started=started, finished=finished, ok=ok, repos=len(repos), failed=len(failed),
        removed=sum(len(o.removed) for o in result.owners),
        bytes=sum(r.bytes or 0 for r in repos),
    ), *runs][:MAX_RUNS]
    if ok:
        result.last_success = finished
    result.as_of = finished
    result.next_due = next_run(finished, s["at"], tz)
    if not ok:
        sent = templates.message(store, "mirror_failed", {"problems": failure_text(result)},
                                 "error")
        await alerts_core.notify(store, cfg, source="github-mirror", category="backup",
                                 severity="error", title=sent.title, body=sent.body,
                                 formatted=sent.html, now=finished, telegram=telegram)
    return result


def failure_text(result: GitHubMirror) -> str:
    if result.error:
        return result.error
    lines = [f"{o.label}: {o.error}" for o in result.owners if o.error]
    failed = [r for o in result.owners for r in o.repos if not r.ok and r.error]
    lines += [f"{r.full_name}: {r.error}" for r in failed[:5]]
    if len(failed) > 5:
        lines.append(f"and {len(failed) - 5} more")
    return "\n".join(lines)


def current(cfg: dict[str, Any], store: Store, now: datetime | None = None) -> dict[str, Any]:
    """The last run, or before the first one a payload saying when it is due."""
    cached = store.get_cache(CACHE_KEY)
    if cached is not None:
        return cached
    s = settings(cfg)
    now = now or datetime.now(UTC)
    return GitHubMirror(
        as_of=now, enabled=s["enabled"], dir=s["dir"],
        next_due=next_run(now, s["at"], cfg.get("timezone", "UTC")) if s["enabled"] else None,
    ).model_dump(mode="json")


def overdue(cfg: dict[str, Any], store: Store, now: datetime) -> bool:
    """Whether to run right away at startup: enabled and the last run missed."""
    if not settings(cfg)["enabled"]:
        return False
    due = (store.get_cache(CACHE_KEY) or {}).get("next_due")
    return due is None or datetime.fromisoformat(due) <= now
