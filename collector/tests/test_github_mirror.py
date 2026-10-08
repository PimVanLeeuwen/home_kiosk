from __future__ import annotations

import asyncio
import base64
import json
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import pytest

from app.alerts import bot, rules
from app.alerts import core as alerts_core
from app.sources import github_mirror

TOKEN = "github_pat_secret"
HUBBLE_TOKEN = "github_pat_hubble"
NOW = datetime(2026, 10, 4, 0, 0, tzinfo=UTC)  # 02:00 in Amsterdam


class FakeTelegram:
    def __init__(self):
        self.sent = []

    async def send(self, chat_id, text):
        self.sent.append((chat_id, text))


def sh(*args: str, cwd: Path | None = None) -> str:
    return subprocess.run(args, cwd=cwd, check=True, capture_output=True, text=True).stdout.strip()


def make_origin(root: Path, owner: str, name: str) -> Path:
    """A bare repo with one commit, standing in for github.com/owner/name."""
    work = root / "work" / owner / name
    work.mkdir(parents=True)
    sh("git", "init", "-q", "-b", "main", cwd=work)
    (work / "README.md").write_text(name)
    commit(work, "first")
    bare = root / "origin" / owner / f"{name}.git"
    sh("git", "clone", "-q", "--bare", str(work), str(bare))
    sh("git", "remote", "add", "github", str(bare), cwd=work)
    return work


def commit(work: Path, message: str) -> None:
    sh("git", "add", "-A", cwd=work)
    sh("git", "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", message, cwd=work)


def node(root: Path, owner: str, name: str, **over) -> dict:
    url = str(root / "origin" / owner / f"{name}.git")
    return {"name": name, "nameWithOwner": f"{owner}/{name}", "url": url,
            "isFork": False, "isArchived": False} | over


def page(nodes, next_cursor=None):
    return {"data": {"repositoryOwner": {"repositories": {
        "pageInfo": {"hasNextPage": next_cursor is not None, "endCursor": next_cursor},
        "nodes": nodes,
    }}}}


@pytest.fixture
def env(tmp_path, store):
    alerts_core.ensure_tables(store)
    base = tmp_path / "backups"
    base.mkdir()
    listing: dict[str, object] = {}
    seen_tokens: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_tokens.append(request.headers["Authorization"])
        login = json.loads(request.content)["variables"]["login"]
        answer = listing[login]
        if isinstance(answer, httpx.Response):
            return answer
        return httpx.Response(200, json=page(answer))

    cfg = {
        "timezone": "Europe/Amsterdam",
        "telegram": {"chats": {"nas": {"id": "-1001"}}},
        "github": {
            "token": TOKEN,
            "owners": [
                {"login": "PimVanLeeuwen", "label": "Mine", "mirror": True},
                {"login": "Hubble-Community-Cafe", "label": "Hubble", "token": HUBBLE_TOKEN,
                 "mirror": True},
                {"login": "GEWIS", "label": "GEWIS", "only_contributed_by": "PimVanLeeuwen"},
            ],
            "mirror": {"dir": str(base), "at": "02:00"},
        },
    }

    class Env:
        pass

    e = Env()
    e.root, e.base, e.cfg, e.store, e.listing, e.tokens = (
        tmp_path, base, cfg, store, listing, seen_tokens)
    e.telegram = FakeTelegram()

    def run(now=NOW):
        result = asyncio.run(github_mirror.collect(
            cfg, store, transport=httpx.MockTransport(handler), now=now, telegram=e.telegram))
        store.put_cache(github_mirror.CACHE_KEY, result.model_dump(mode="json"))
        return result

    e.run = run
    return e


def heads(repo: Path) -> str:
    return sh("git", "--git-dir", str(repo), "rev-parse", "refs/heads/main")


def test_mirrors_owned_repos_without_forks_or_collaborations(env):
    for owner, name in [("PimVanLeeuwen", "home_kiosk"), ("PimVanLeeuwen", "old-thing"),
                        ("Hubble-Community-Cafe", "web")]:
        make_origin(env.root, owner, name)
    env.listing["PimVanLeeuwen"] = [
        node(env.root, "PimVanLeeuwen", "home_kiosk"),
        node(env.root, "PimVanLeeuwen", "old-thing", isArchived=True),
        node(env.root, "PimVanLeeuwen", "upstream", isFork=True),
        node(env.root, "SomeoneElse", "shared"),
        None,
    ]
    env.listing["Hubble-Community-Cafe"] = [node(env.root, "Hubble-Community-Cafe", "web")]

    result = env.run()

    assert result.error is None
    assert [o.login for o in result.owners] == ["PimVanLeeuwen", "Hubble-Community-Cafe"]
    mine = result.owners[0]
    assert [(r.full_name, r.archived, r.ok) for r in mine.repos] == [
        ("PimVanLeeuwen/home_kiosk", False, True), ("PimVanLeeuwen/old-thing", True, True)]
    assert all(r.mirrored_at == NOW and r.bytes for r in mine.repos)
    assert sorted(p.name for p in (env.base / "PimVanLeeuwen").iterdir()) == [
        "home_kiosk.git", "old-thing.git"]
    assert (env.base / "Hubble-Community-Cafe" / "web.git" / "HEAD").exists()
    # Each owner is listed with its own token; GEWIS is not mirrored.
    assert env.tokens == [f"Bearer {TOKEN}", f"Bearer {HUBBLE_TOKEN}"]
    (run,) = result.runs
    assert (run.ok, run.repos, run.failed, run.removed) == (True, 3, 0, 0)
    assert run.bytes == sum(r.bytes for o in result.owners for r in o.repos)
    assert result.last_success == NOW
    # 02:00 Amsterdam the next night.
    assert result.next_due == datetime(2026, 10, 5, 0, 0, tzinfo=UTC)
    assert env.telegram.sent == []


def test_next_run_fetches_new_commits_and_removes_deleted_repos(env):
    work = make_origin(env.root, "PimVanLeeuwen", "home_kiosk")
    make_origin(env.root, "PimVanLeeuwen", "gone")
    env.listing["PimVanLeeuwen"] = [node(env.root, "PimVanLeeuwen", "home_kiosk"),
                                    node(env.root, "PimVanLeeuwen", "gone")]
    env.listing["Hubble-Community-Cafe"] = []
    env.run()

    (work / "README.md").write_text("changed")
    commit(work, "second")
    sh("git", "push", "-q", "github", "main", cwd=work)
    env.listing["PimVanLeeuwen"] = [node(env.root, "PimVanLeeuwen", "home_kiosk")]
    # A clone cut off half-way by a restart.
    (env.base / "PimVanLeeuwen" / "new.git.partial").mkdir()
    (env.base / "PimVanLeeuwen" / "notes.txt").write_text("left alone")

    later = NOW + timedelta(days=1)
    result = env.run(later)

    mirror = env.base / "PimVanLeeuwen" / "home_kiosk.git"
    assert heads(mirror) == sh("git", "rev-parse", "HEAD", cwd=work)
    assert sorted(p.name for p in (env.base / "PimVanLeeuwen").iterdir()) == [
        "home_kiosk.git", "notes.txt"]
    assert result.owners[0].removed == ["PimVanLeeuwen/gone"]
    assert [r.removed for r in result.runs] == [1, 0]
    assert result.last_success == later


def test_a_failing_repo_fails_the_run_keeps_its_last_success_and_alerts(env):
    make_origin(env.root, "PimVanLeeuwen", "home_kiosk")
    make_origin(env.root, "PimVanLeeuwen", "flaky")
    env.listing["PimVanLeeuwen"] = [node(env.root, "PimVanLeeuwen", "home_kiosk"),
                                    node(env.root, "PimVanLeeuwen", "flaky")]
    env.listing["Hubble-Community-Cafe"] = []
    env.run()

    env.listing["PimVanLeeuwen"][1]["url"] = str(env.root / "origin" / "nowhere.git")
    later = NOW + timedelta(days=1)
    result = env.run(later)

    ok, flaky = result.owners[0].repos
    assert (ok.ok, ok.mirrored_at) == (True, later)
    assert (flaky.ok, flaky.mirrored_at) == (False, NOW)
    assert flaky.error and TOKEN not in flaky.error
    # The existing mirror is kept, as it was.
    assert (env.base / "PimVanLeeuwen" / "flaky.git" / "HEAD").exists()
    assert (result.runs[0].ok, result.runs[0].failed) == (False, 1)
    assert result.last_success == NOW
    ((chat, text),) = env.telegram.sent
    assert chat == "-1001"
    assert "GitHub mirror failed" in text and "PimVanLeeuwen/flaky" in text


def test_a_failed_listing_touches_nothing(env):
    make_origin(env.root, "PimVanLeeuwen", "home_kiosk")
    env.listing["PimVanLeeuwen"] = [node(env.root, "PimVanLeeuwen", "home_kiosk")]
    env.listing["Hubble-Community-Cafe"] = []
    env.run()

    env.listing["PimVanLeeuwen"] = httpx.Response(401)
    result = env.run(NOW + timedelta(days=1))

    mine = result.owners[0]
    assert mine.error == "Token refused (401)"
    assert [(r.full_name, r.ok, r.mirrored_at) for r in mine.repos] == [
        ("PimVanLeeuwen/home_kiosk", False, NOW)]
    assert (env.base / "PimVanLeeuwen" / "home_kiosk.git").is_dir()
    assert not result.runs[0].ok
    assert "Mine: Token refused (401)" in env.telegram.sent[0][1]


def test_too_many_pages_is_an_error_not_a_partial_list(env, monkeypatch):
    make_origin(env.root, "PimVanLeeuwen", "home_kiosk")
    env.listing["Hubble-Community-Cafe"] = []
    env.listing["PimVanLeeuwen"] = [node(env.root, "PimVanLeeuwen", "home_kiosk")]
    env.run()
    monkeypatch.setattr(github_mirror, "MAX_PAGES", 1)

    def endless(request):
        return httpx.Response(200, json=page([], next_cursor="more"))

    result = asyncio.run(github_mirror.collect(
        env.cfg, env.store, transport=httpx.MockTransport(endless), now=NOW,
        telegram=env.telegram))

    assert result.owners[0].error == "More than 100 repos for PimVanLeeuwen"
    assert (env.base / "PimVanLeeuwen" / "home_kiosk.git").is_dir()


def test_unsafe_names_are_never_used_as_folders(env):
    env.listing["PimVanLeeuwen"] = [node(env.root, "PimVanLeeuwen", ".."),
                                    node(env.root, "PimVanLeeuwen", "a/b")]
    env.listing["Hubble-Community-Cafe"] = []

    result = env.run()

    assert result.owners[0].repos == []
    assert result.runs[0].ok


def test_a_missing_mount_is_reported_and_never_created(env):
    env.cfg["github"]["mirror"]["dir"] = str(env.root / "not-mounted")

    result = env.run()

    assert "not found" in result.error
    assert not (env.root / "not-mounted").exists()
    assert not result.runs[0].ok
    assert "not found" in env.telegram.sent[0][1]


def test_off_without_mirror_owners(env):
    for owner in env.cfg["github"]["owners"]:
        owner.pop("mirror", None)

    result = env.run()

    assert (result.enabled, result.runs, result.owners) == (False, [], [])
    assert not github_mirror.overdue(env.cfg, env.store, NOW)


def test_git_gets_the_token_only_as_a_github_header():
    env = github_mirror.git_env(TOKEN)

    assert env["GIT_TERMINAL_PROMPT"] == "0"
    assert env["GIT_CONFIG_KEY_0"] == "http.https://github.com/.extraHeader"
    value = env["GIT_CONFIG_VALUE_0"].removeprefix("Authorization: Basic ")
    assert base64.b64decode(value).decode() == f"x-access-token:{TOKEN}"
    assert github_mirror.clone_url("https://github.com/o/r") == "https://github.com/o/r.git"
    assert github_mirror.clone_url("/local/r.git") == "/local/r.git"


def test_no_token_ends_up_in_the_mirror(env):
    make_origin(env.root, "PimVanLeeuwen", "home_kiosk")
    env.listing["PimVanLeeuwen"] = [node(env.root, "PimVanLeeuwen", "home_kiosk")]
    env.listing["Hubble-Community-Cafe"] = []
    env.run()

    config = (env.base / "PimVanLeeuwen" / "home_kiosk.git" / "config").read_text()
    assert TOKEN not in config and "extraHeader" not in config


def test_current_and_overdue_before_and_after_the_first_run(env):
    before = github_mirror.current(env.cfg, env.store, NOW)
    assert (before["enabled"], before["runs"]) == (True, [])
    assert datetime.fromisoformat(before["next_due"]) == datetime(2026, 10, 5, 0, 0, tzinfo=UTC)
    assert github_mirror.overdue(env.cfg, env.store, NOW)

    env.listing["PimVanLeeuwen"] = []
    env.listing["Hubble-Community-Cafe"] = []
    env.run()

    assert not github_mirror.overdue(env.cfg, env.store, NOW + timedelta(hours=23))
    assert github_mirror.overdue(env.cfg, env.store, NOW + timedelta(hours=25))


def mirror_payload(last_success, runs=1, enabled=True):
    run = {"started": NOW.isoformat(), "finished": NOW.isoformat(), "ok": last_success is not None,
           "repos": 12, "failed": 0 if last_success else 2, "removed": 0, "bytes": 1_300_000_000}
    return {"enabled": enabled, "runs": [run] * runs, "owners": [],
            "last_success": last_success.isoformat() if last_success else None}


def test_backup_missing_covers_the_mirror():
    settings = {"hours": 26}
    later = NOW + timedelta(hours=30)
    marker = {"backup": {"status": "ok", "at": later.isoformat()}}

    (late,) = rules.backup_missing(None, marker, settings, later, mirror_payload(NOW))
    assert (late.key, late.title) == ("backup_missing:github-mirror",
                                      "No complete GitHub mirror in 26 h")
    assert rules.backup_missing(None, marker, settings, NOW, mirror_payload(NOW)) == []
    (never,) = rules.backup_missing(None, marker, settings, NOW, mirror_payload(None))
    assert never.body == "Last success: none recorded"
    # Before the first run, or when off, it is not judged.
    assert rules.backup_missing(None, marker, settings, later, mirror_payload(None, runs=0)) == []
    assert rules.backup_missing(None, marker, settings, later,
                                mirror_payload(None, enabled=False)) == []


def test_bot_backup_reply_mentions_the_mirror(store):
    cfg = {"timezone": "Europe/Amsterdam"}
    store.put_cache("backups", {"runs": [{"ok": True, "finished": NOW.isoformat(),
                                          "volumes": []}], "next_due": None})
    assert "GitHub mirror" not in bot.backup_text(store, cfg)

    store.put_cache("github_mirror", mirror_payload(NOW))
    assert bot.backup_text(store, cfg).endswith(
        "\n\n<b>GitHub mirror</b>: OK · 12 repos · 1,3 GB\nSun 04 Oct 02:00")

    store.put_cache("github_mirror", mirror_payload(None))
    assert "GitHub mirror</b>: failed (2 of 12 repos)" in bot.backup_text(store, cfg)
