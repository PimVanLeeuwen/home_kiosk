from __future__ import annotations

import asyncio
import json
import logging

import httpx

from app.sources import github

TOKEN = "github_pat_secret"
HUBBLE_TOKEN = "github_pat_hubble"


def node(name: str, owner: str = "PimVanLeeuwen", **over) -> dict:
    base = {
        "name": name, "nameWithOwner": f"{owner}/{name}", "url": f"https://github.com/{owner}/{name}",
        "description": f"{name} repo", "isPrivate": False, "isFork": False, "isArchived": False,
        "primaryLanguage": {"name": "Python", "color": "#3572A5"},
        "stargazerCount": 3, "forkCount": 1, "pushedAt": "2026-09-30T18:00:00Z",
        "pullRequests": {"totalCount": 2}, "issues": {"totalCount": 5},
        "latestRelease": {"tagName": "v1.2.0", "publishedAt": "2026-09-01T10:00:00Z",
                          "url": f"https://github.com/{owner}/{name}/releases/tag/v1.2.0"},
        "defaultBranchRef": {"target": {"statusCheckRollup": {"state": "SUCCESS"}}},
    }
    base.update(over)
    return base


def page(nodes, next_cursor=None):
    return {"data": {"repositoryOwner": {"repositories": {
        "pageInfo": {"hasNextPage": next_cursor is not None, "endCursor": next_cursor},
        "nodes": nodes,
    }}}}


def run(store, handler, owners, token=TOKEN):
    cfg = {"github": {"token": token, "owners": owners}}
    return asyncio.run(github.collect(cfg, store, transport=httpx.MockTransport(handler)))


def test_parse_repo_maps_fields_and_ci_states():
    repo = github.parse_repo(node("home_kiosk", isPrivate=True))

    assert (repo.full_name, repo.private, repo.language, repo.stars, repo.open_prs,
            repo.open_issues, repo.ci, repo.release.tag) == (
        "PimVanLeeuwen/home_kiosk", True, "Python", 3, 2, 5, "passing", "v1.2.0")

    def ci(state):
        target = {"target": {"statusCheckRollup": {"state": state} if state else None}}
        return github.parse_repo(node("x", defaultBranchRef=target)).ci

    assert [ci(s) for s in ["FAILURE", "ERROR", "PENDING", "EXPECTED", None]] == [
        "failing", "failing", "running", "running", "none"]
    bare = github.parse_repo(node("x", primaryLanguage=None, latestRelease=None,
                                  defaultBranchRef=None, description=None))
    assert (bare.language, bare.release, bare.ci, bare.description) == (None, None, "none", None)


def test_owner_repos_page_through_and_skip_archived(store):
    seen = []

    def handler(request):
        body = json.loads(request.content)
        seen.append((request.headers["authorization"], body["variables"]))
        if body["variables"]["cursor"] is None:
            return httpx.Response(200, json=page([node("a"), node("old", isArchived=True)], "c1"))
        return httpx.Response(200, json=page([node("b")]))

    result = run(store, handler, [{"login": "PimVanLeeuwen", "label": "Mine"}])

    group = result.groups[0]
    assert (group.label, group.error, [r.name for r in group.repos]) == ("Mine", None, ["a", "b"])
    assert seen == [
        (f"Bearer {TOKEN}", {"login": "PimVanLeeuwen", "cursor": None}),
        (f"Bearer {TOKEN}", {"login": "PimVanLeeuwen", "cursor": "c1"}),
    ]


def test_an_owner_can_have_its_own_token(store):
    tokens = []

    def handler(request):
        tokens.append(request.headers["authorization"])
        return httpx.Response(200, json=page([node("web", owner="Hubble-Community-Cafe")]))

    run(store, handler, [
        {"login": "PimVanLeeuwen"},
        {"login": "Hubble-Community-Cafe", "token": HUBBLE_TOKEN},
        {"login": "Other", "token": ""},  # empty falls back to the main token
    ])

    assert tokens == [f"Bearer {TOKEN}", f"Bearer {HUBBLE_TOKEN}", f"Bearer {TOKEN}"]


def test_contributed_repos_come_from_pr_and_commit_searches(store):
    queries = []

    def handler(request):
        if request.url.path == "/search/commits":
            assert request.url.params["q"] == "author:PimVanLeeuwen org:GEWIS"
            return httpx.Response(200, json={"items": [
                {"repository": {"full_name": "GEWIS/aurora"}},
                {"repository": {"full_name": "GEWIS/food"}},
            ]})
        body = json.loads(request.content)
        queries.append(body["query"])
        if "search(" in body["query"]:
            assert body["variables"]["q"] == "is:pr author:PimVanLeeuwen org:GEWIS"
            return httpx.Response(200, json={"data": {"search": {"nodes": [
                {"repository": {"nameWithOwner": "GEWIS/aurora"}},
                {"repository": {"nameWithOwner": "GEWIS/aurora-client"}},
                {},
            ]}}})
        return httpx.Response(200, json={"data": {
            "r0": node("aurora", owner="GEWIS", pushedAt="2026-09-29T00:00:00Z"),
            "r1": node("aurora-client", owner="GEWIS", isArchived=True),
            "r2": node("food", owner="GEWIS", pushedAt="2026-09-30T00:00:00Z"),
        }})

    result = run(store, handler, [
        {"login": "GEWIS", "label": "GEWIS", "only_contributed_by": "PimVanLeeuwen"},
    ])

    # Archived repos are hidden; the rest newest first.
    assert [r.name for r in result.groups[0].repos] == ["food", "aurora"]
    aliased = queries[-1]
    assert 'r0: repository(owner: "GEWIS", name: "aurora")' in aliased
    assert 'r2: repository(owner: "GEWIS", name: "food")' in aliased


def test_failures_keep_the_last_list_with_a_short_reason(store):
    store.put_cache("repos", {"as_of": "2026-09-30T12:00:00+00:00", "stale": False, "groups": [
        {"login": "PimVanLeeuwen", "label": "Mine",
         "repos": [github.parse_repo(node("kept")).model_dump(mode="json")], "error": None},
    ]})

    def handler(request):
        body = json.loads(request.content)
        if body["variables"]["login"] == "PimVanLeeuwen":
            return httpx.Response(401)
        return httpx.Response(200, json={"errors": [
            {"message": "Resource not accessible by personal access token"}]})

    result = run(store, handler, [{"login": "PimVanLeeuwen"}, {"login": "Hubble-Community-Cafe"}])

    mine, hubble = result.groups
    assert (mine.error, [r.name for r in mine.repos]) == ("Token refused (401)", ["kept"])
    assert hubble.error == "GitHub refused: Resource not accessible by personal access token"
    assert hubble.repos == []


def test_unknown_owner_and_missing_token(store):
    def handler(request):
        return httpx.Response(200, json={"data": {"repositoryOwner": None}})

    assert run(store, handler, [{"login": "nobody"}]).groups[0].error == (
        "No GitHub user or organisation called nobody")
    assert run(store, handler, [{"login": "x"}], token="").groups[0].error == (
        "No GitHub token set (GITHUB_TOKEN)")


def test_tokens_never_reach_errors_or_logs(store, caplog):
    def handler(request):
        raise httpx.ConnectError(f"boom {request.headers['authorization']}", request=request)

    with caplog.at_level(logging.DEBUG):
        result = run(store, handler, [{"login": "PimVanLeeuwen"}])

    assert result.groups[0].error == "GitHub not reachable"
    assert TOKEN not in caplog.text
    assert TOKEN not in result.model_dump_json()


def test_each_token_reports_its_expiry_and_never_its_value(store):
    owners = [{"login": "PimVanLeeuwen", "label": "Mine"},
              {"login": "Hubble-Community-Cafe", "label": "Hubble", "token": HUBBLE_TOKEN},
              {"login": "Other", "label": "Other"}]

    def handler(request):
        headers = {}
        if request.headers["Authorization"] == f"Bearer {TOKEN}":
            headers[github.EXPIRY_HEADER] = "2026-11-21 13:05:00 UTC"
        return httpx.Response(200, json=page([node("x")]), headers=headers)

    repos = run(store, handler, owners)

    mine, hubble = repos.tokens
    assert (mine.owners, mine.checked, mine.expires_at.isoformat()) == (
        ["Mine", "Other"], True, "2026-11-21T13:05:00+00:00")
    # Answered without the header: a token with no expiry date.
    assert (hubble.owners, hubble.checked, hubble.expires_at) == (["Hubble"], True, None)
    dumped = repos.model_dump_json()
    assert TOKEN not in dumped and HUBBLE_TOKEN not in dumped


def test_a_token_github_refused_keeps_what_was_known(store):
    store.put_cache("repos", {"groups": [], "tokens": [
        {"owners": ["Mine"], "expires_at": "2026-11-21T13:05:00+00:00", "checked": True}]})

    repos = run(store, lambda request: httpx.Response(401), [{"login": "PimVanLeeuwen",
                                                               "label": "Mine"}])

    assert repos.tokens[0].expires_at.isoformat() == "2026-11-21T13:05:00+00:00"


def test_expiry_header_formats():
    assert github.parse_expiry("2026-11-21 13:05:00 +0100").isoformat() == (
        "2026-11-21T13:05:00+01:00")
    assert github.parse_expiry("next tuesday") is None
