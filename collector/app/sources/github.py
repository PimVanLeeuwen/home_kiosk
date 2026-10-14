"""GitHub repos for the Repos page: yours, Hubble's, and GEWIS repos you
contributed to.

One GraphQL query per owner returns every field the page shows (cost 1 of the
5,000 hourly points). For owners limited to your contributions, two searches
(pull requests via GraphQL, commits via REST, which GraphQL cannot search) find
the repos, then one aliased query fetches them. Read-only: the tokens need
read access only, and nothing is ever written to GitHub.
"""

from __future__ import annotations

import logging
from datetime import UTC, date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import httpx

from ..models import (
    Activity,
    ContributionDay,
    GitHubToken,
    PullRequest,
    Release,
    Repo,
    RepoGroup,
    Repos,
)
from ..store import Store

log = logging.getLogger(__name__)

API = "https://api.github.com"
TIMEOUT_SECONDS = 20
MAX_PAGES = 5  # 500 repos per owner is plenty
ACTIVITY_WEEKS = 16

REPO_FIELDS = """
fragment RepoFields on Repository {
  name nameWithOwner url description isPrivate isFork isArchived
  primaryLanguage { name color }
  stargazerCount forkCount pushedAt
  pullRequests(states: OPEN) { totalCount }
  openPulls: pullRequests(states: OPEN, first: 5, orderBy: {field: UPDATED_AT, direction: DESC}) {
    nodes {
      number title url isDraft updatedAt
      commits(last: 1) { nodes { commit { statusCheckRollup { state } } } }
    }
  }
  issues(states: OPEN) { totalCount }
  latestRelease { tagName publishedAt url }
  defaultBranchRef {
    name
    target { ... on Commit { messageHeadline committedDate statusCheckRollup { state } } }
  }
}
"""

OWNER_QUERY = """
query($login: String!, $cursor: String) {
  repositoryOwner(login: $login) {
    repositories(first: 100, after: $cursor, isArchived: false,
                 orderBy: {field: PUSHED_AT, direction: DESC}) {
      pageInfo { hasNextPage endCursor }
      nodes { ...RepoFields }
    }
  }
}
""" + REPO_FIELDS

CONTRIBUTED_PRS_QUERY = """
query($q: String!) {
  search(query: $q, type: ISSUE, first: 100) {
    nodes { ... on PullRequest { repository { nameWithOwner } } }
  }
}
"""

CONTRIBUTIONS_QUERY = """
query($login: String!, $from: DateTime!, $to: DateTime!) {
  user(login: $login) {
    contributionsCollection(from: $from, to: $to) {
      contributionCalendar {
        weeks { contributionDays { date contributionCount contributionLevel } }
      }
    }
  }
}
"""

LEVEL = {"NONE": 0, "FIRST_QUARTILE": 1, "SECOND_QUARTILE": 2, "THIRD_QUARTILE": 3,
         "FOURTH_QUARTILE": 4}

CI_STATE = {
    "SUCCESS": "passing",
    "FAILURE": "failing",
    "ERROR": "failing",
    "PENDING": "running",
    "EXPECTED": "running",
}


EXPIRY_HEADER = "github-authentication-token-expiration"


class GitHubError(Exception):
    """A failure with a message fit for the page."""


def parse_expiry(value: str) -> datetime | None:
    """GitHub's expiry header, such as "2026-11-21 13:05:00 UTC" or "... +0100"."""
    text = value.strip().replace(" UTC", " +0000")
    try:
        return datetime.strptime(text, "%Y-%m-%d %H:%M:%S %z")
    except ValueError:
        log.warning("unreadable token expiry header")
        return None


def _ci(commit: dict[str, Any] | None) -> str:
    rollup = ((commit or {}).get("statusCheckRollup") or {}).get("state")
    return CI_STATE.get(rollup or "", "none")


def parse_pull(node: dict[str, Any]) -> PullRequest:
    last = ((node.get("commits") or {}).get("nodes") or [None])[-1] or {}
    return PullRequest(number=node["number"], title=node["title"], url=node["url"],
                       draft=bool(node.get("isDraft")), updated_at=node.get("updatedAt"),
                       ci=_ci(last.get("commit")))


def parse_repo(node: dict[str, Any]) -> Repo:
    language = node.get("primaryLanguage") or {}
    release = node.get("latestRelease")
    branch = node.get("defaultBranchRef") or {}
    target = branch.get("target") or {}
    return Repo(
        name=node["name"],
        full_name=node["nameWithOwner"],
        url=node["url"],
        description=node.get("description"),
        private=bool(node.get("isPrivate")),
        fork=bool(node.get("isFork")),
        language=language.get("name"),
        language_color=language.get("color"),
        stars=node.get("stargazerCount", 0),
        forks=node.get("forkCount", 0),
        pushed_at=node.get("pushedAt"),
        open_prs=(node.get("pullRequests") or {}).get("totalCount", 0),
        open_issues=(node.get("issues") or {}).get("totalCount", 0),
        ci=_ci(target),
        release=Release(
            tag=release["tagName"], published_at=release.get("publishedAt"), url=release["url"]
        )
        if release
        else None,
        branch=branch.get("name"),
        commit_message=target.get("messageHeadline"),
        committed_at=target.get("committedDate"),
        pulls=[parse_pull(n) for n in (node.get("openPulls") or {}).get("nodes") or [] if n],
    )


def describe(exc: Exception) -> str:
    """A short reason without URLs, headers or tokens."""
    if isinstance(exc, GitHubError):
        return str(exc)
    if isinstance(exc, httpx.HTTPStatusError):
        code = exc.response.status_code
        if code == 401:
            return "Token refused (401)"
        if code == 403:
            return "Not allowed or rate limited (403)"
        return f"GitHub answered {code}"
    if isinstance(exc, httpx.TimeoutException):
        return "GitHub timed out"
    if isinstance(exc, httpx.TransportError):
        return "GitHub not reachable"
    return "Unexpected response from GitHub"


async def _graphql(
    client: httpx.AsyncClient, token: str, query: str, variables: dict[str, Any]
) -> dict[str, Any]:
    resp = await client.post(
        f"{API}/graphql",
        json={"query": query, "variables": variables},
        headers={"Authorization": f"Bearer {token}"},
    )
    resp.raise_for_status()
    body = resp.json()
    data = body.get("data")
    if not data:
        # GraphQL reports access problems as 200 with errors; their messages
        # name the resource, never the token.
        message = ((body.get("errors") or [{}])[0].get("message") or "no data")[:120]
        raise GitHubError(f"GitHub refused: {message}")
    return data


async def owner_repos(client: httpx.AsyncClient, token: str, login: str) -> list[Repo]:
    repos: list[Repo] = []
    cursor = None
    for _ in range(MAX_PAGES):
        data = await _graphql(client, token, OWNER_QUERY, {"login": login, "cursor": cursor})
        owner = data.get("repositoryOwner")
        if owner is None:
            raise GitHubError(f"No GitHub user or organisation called {login}")
        page = owner["repositories"]
        repos += [parse_repo(n) for n in page["nodes"] if n and not n.get("isArchived")]
        if not page["pageInfo"]["hasNextPage"]:
            break
        cursor = page["pageInfo"]["endCursor"]
    return repos


async def contributed_names(
    client: httpx.AsyncClient, token: str, login: str, author: str
) -> list[str]:
    """Repos of `login` with your pull requests or default-branch commits, all time."""
    prs = await _graphql(
        client, token, CONTRIBUTED_PRS_QUERY, {"q": f"is:pr author:{author} org:{login}"}
    )
    names = {
        n["repository"]["nameWithOwner"]
        for n in prs["search"]["nodes"]
        if n and n.get("repository")
    }
    resp = await client.get(
        f"{API}/search/commits",
        params={"q": f"author:{author} org:{login}", "per_page": 100},
        headers={"Authorization": f"Bearer {token}"},
    )
    resp.raise_for_status()
    names |= {item["repository"]["full_name"] for item in resp.json().get("items", [])}
    return sorted(names)


async def named_repos(client: httpx.AsyncClient, token: str, names: list[str]) -> list[Repo]:
    if not names:
        return []
    fields = "\n".join(
        f'r{i}: repository(owner: "{n.split("/")[0]}", name: "{n.split("/")[1]}") '
        "{ ...RepoFields }"
        for i, n in enumerate(names)
    )
    data = await _graphql(client, token, f"query {{\n{fields}\n}}" + REPO_FIELDS, {})
    repos = [parse_repo(node) for node in data.values() if node and not node.get("isArchived")]
    return sorted(repos, key=lambda r: r.pushed_at or datetime.min.replace(tzinfo=UTC),
                  reverse=True)


async def _group(
    client: httpx.AsyncClient, owner: dict[str, Any], default_token: str,
    previous: dict[str, Any] | None,
) -> RepoGroup:
    login, label = owner["login"], owner.get("label", owner["login"])
    own = not owner.get("only_contributed_by")
    token = (owner.get("token") or "").strip() or default_token
    try:
        if not token:
            raise GitHubError("No GitHub token set (GITHUB_TOKEN)")
        if owner.get("only_contributed_by"):
            names = await contributed_names(client, token, login, owner["only_contributed_by"])
            repos = await named_repos(client, token, names)
        else:
            repos = await owner_repos(client, token, login)
        return RepoGroup(login=login, label=label, repos=repos, own=own)
    except Exception as exc:
        log.warning("github repos for %s failed: %s", login, type(exc).__name__)
        last = (previous or {}).get("repos", [])
        return RepoGroup(login=login, label=label, repos=last, error=describe(exc), own=own)


def activity_start(today: date) -> date:
    """The Monday that opens the 16 weeks ending with this one."""
    return today - timedelta(days=today.weekday(), weeks=ACTIVITY_WEEKS - 1)


async def contributions(client: httpx.AsyncClient, token: str, login: str,
                        now: datetime) -> Activity:
    start = activity_start(now.date())
    since = datetime.combine(start, datetime.min.time(), now.tzinfo)
    data = await _graphql(client, token, CONTRIBUTIONS_QUERY, {
        "login": login, "from": since.isoformat(), "to": now.isoformat()})
    if data.get("user") is None:
        raise GitHubError(f"No GitHub user called {login}")
    weeks = data["user"]["contributionsCollection"]["contributionCalendar"]["weeks"]
    days = [
        ContributionDay(day=d["date"], count=d["contributionCount"],
                        level=LEVEL.get(d["contributionLevel"], 0))
        for week in weeks for d in week["contributionDays"]
        if start <= date.fromisoformat(d["date"]) <= now.date()
    ]
    return Activity(login=login, total=sum(d.count for d in days), days=days)


async def _activity(client: httpx.AsyncClient, login: str, token: str, now: datetime,
                    previous: dict[str, Any] | None) -> Activity | None:
    try:
        if not token:
            raise GitHubError("No GitHub token set (GITHUB_TOKEN)")
        return await contributions(client, token, login, now)
    except Exception as exc:
        log.warning("github activity failed: %s", type(exc).__name__)
        if previous and previous.get("login") == login:
            return Activity.model_validate(previous | {"error": describe(exc)})
        return Activity(login=login, total=0, days=[], error=describe(exc))


def _tokens(
    owners: list[dict[str, Any]], default_token: str, answered: dict[str, str | None],
    previous: list[dict[str, Any]],
) -> list[GitHubToken]:
    """One entry per distinct token, named by the owners it reads. `answered`
    maps an Authorization header to the expiry GitHub sent with it (None when
    it sent none: no expiry date). A token GitHub did not answer this time
    keeps what the last run knew."""
    by_token: dict[str, list[str]] = {}
    for owner in owners:
        token = (owner.get("token") or "").strip() or default_token
        if token:
            by_token.setdefault(token, []).append(owner.get("label", owner["login"]))
    known = {tuple(t["owners"]): t for t in previous}
    tokens = []
    for token, labels in by_token.items():
        auth = f"Bearer {token}"
        if auth in answered:
            expiry = answered[auth]
            tokens.append(GitHubToken(owners=labels, checked=True,
                                      expires_at=parse_expiry(expiry) if expiry else None))
        elif (last := known.get(tuple(labels))) is not None:
            tokens.append(GitHubToken.model_validate(last))
        else:
            tokens.append(GitHubToken(owners=labels))
    return tokens


async def collect(
    cfg: dict[str, Any], store: Store, transport: httpx.AsyncBaseTransport | None = None,
    now: datetime | None = None,
) -> Repos:
    """`transport` is for tests (httpx.MockTransport)."""
    now = now or datetime.now(ZoneInfo(cfg.get("timezone", "UTC")))
    gh_cfg = cfg.get("github") or {}
    default_token = (gh_cfg.get("token") or "").strip()
    cached = store.get_cache("repos") or {}
    previous = {g["login"]: g for g in cached.get("groups", [])}
    # Authorization header -> the token's expiry, from every answered request.
    answered: dict[str, str | None] = {}

    async def note_expiry(response: httpx.Response) -> None:
        auth = response.request.headers.get("Authorization")
        if auth and response.status_code < 400:
            answered[auth] = response.headers.get(EXPIRY_HEADER) or answered.get(auth)

    async with httpx.AsyncClient(
        timeout=TIMEOUT_SECONDS,
        transport=transport,
        headers={"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"},
        event_hooks={"response": [note_expiry]},
    ) as client:
        groups = [
            await _group(client, owner, default_token, previous.get(owner["login"]))
            for owner in gh_cfg.get("owners", [])
        ]
        login = (gh_cfg.get("contributions") or "").strip()
        activity = await _activity(client, login, default_token, now,
                                   cached.get("activity")) if login else None
    tokens = _tokens(gh_cfg.get("owners", []), default_token, answered, cached.get("tokens", []))
    return Repos(as_of=datetime.now(UTC), stale=False, groups=groups, tokens=tokens,
                 activity=activity)
