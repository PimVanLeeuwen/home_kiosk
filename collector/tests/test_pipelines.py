from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from fastapi.testclient import TestClient

from app import main
from app.sources import pipelines

NOW = datetime(2026, 10, 21, 12, 30, tzinfo=UTC)
CFG = {
    "github": {
        "token": "mine",
        "owners": [{"login": "Example", "token": ""}, {"login": "Club", "token": "club"}],
    },
    "pipelines": {"repos": [{"repo": "Club/cafe", "workflow": "ci.yml"}]},
}

# Shaped like community-cafe-web's CI: tests, an approval gate, matrix builds, releases.
WORKFLOW = """
on: [push, pull_request]
jobs:
  backend:
    name: Backend (Maven)
  frontend:
    name: Frontend (${{ matrix.app }})
    strategy: {matrix: {app: [admin, public]}}
  check:
    name: Version Check
    if: github.event_name == 'pull_request'
  approve:
    name: Await publish approval
    needs: [backend, frontend]
  images:
    name: Build & push (${{ matrix.service }})
    needs: approve
  release:
    name: GitHub Release
    needs: [images, check]
"""


def at(minutes: float) -> str:
    return (NOW - timedelta(minutes=minutes)).isoformat().replace("+00:00", "Z")


def job(name, status="completed", conclusion="success", started=20, ended=15):
    return {
        "name": name,
        "status": status,
        "conclusion": conclusion,
        "started_at": at(started) if started is not None else None,
        "completed_at": at(ended) if ended is not None else None,
    }


def run(id, number, status="completed", conclusion="success", started=60, updated=50, sha=None):
    return {
        "id": id,
        "run_number": number,
        "status": status,
        "conclusion": conclusion,
        "head_sha": sha or f"{id:040x}",
        "path": ".github/workflows/ci.yml",
        "html_url": f"https://github.com/Club/cafe/actions/runs/{id}",
        "created_at": at(started),
        "run_started_at": at(started),
        "updated_at": at(updated),
        "head_commit": {"message": "feat: menu cards\n\nlonger text", "author": {"name": "A"}},
    }


GOOD_JOBS = [
    job("Backend (Maven)", started=60, ended=58),
    job("Frontend (admin)", started=60, ended=59),
    job("Frontend (public)", started=60, ended=59),
    job("Version Check", conclusion="skipped", started=60, ended=60),
    job("Await publish approval", started=57, ended=57),
    job("Build & push (admin)", started=57, ended=53),
    job("Build & push (backend)", started=57, ended=52),
    job("GitHub Release", started=52, ended=51),
]


class GitHub:
    """The REST answers for one repo, and every request seen."""

    def __init__(self, runs, jobs_by_run, fail=False):
        self.runs, self.jobs, self.fail, self.seen = runs, jobs_by_run, fail, []

    def transport(self):
        def handler(request: httpx.Request):
            self.seen.append(request)
            if self.fail:
                return httpx.Response(502)
            path = request.url.path
            if path.endswith("/actions/workflows/ci.yml/runs"):
                assert dict(request.url.params) == {
                    "branch": "main",
                    "event": "push",
                    "per_page": "15",
                }
                return httpx.Response(200, json={"workflow_runs": self.runs})
            if path.endswith("/contents/.github/workflows/ci.yml"):
                assert request.headers["accept"] == "application/vnd.github.raw+json"
                return httpx.Response(200, text=WORKFLOW)
            if "/actions/runs/" in path and path.endswith("/jobs"):
                return httpx.Response(200, json={"jobs": self.jobs[int(path.split("/")[-2])]})
            return httpx.Response(404)

        return httpx.MockTransport(handler)


@pytest.fixture(autouse=True)
def fresh():
    pipelines.reset()


def collect(store, gh, now=NOW, cfg=CFG):
    return asyncio.run(pipelines.collect(cfg, store, transport=gh.transport(), now=now))


def test_the_workflow_file_gives_stages_and_names():
    graph = pipelines.parse_workflow(WORKFLOW)
    assert pipelines.columns(graph) == {
        "backend": 0,
        "frontend": 0,
        "check": 0,
        "approve": 1,
        "images": 2,
        "release": 3,
    }
    assert pipelines.display(graph["images"]["name"]) == "Build & push"
    assert graph["images"]["needs"] == ["approve"]


def test_an_idle_repo_has_its_recent_runs_and_no_current_one(store):
    runs = [
        run(3, 103, started=300, updated=290),
        run(2, 102, conclusion="failure", started=900, updated=880),
        run(1, 101, started=2000, updated=1990),
    ]
    state = collect(store, GitHub(runs, {})).repos[0]

    assert (state.name, state.branch, state.run) == ("cafe", "main", None)
    assert [(r.ok, r.seconds) for r in state.recent] == [(True, 600), (False, 1200), (True, 600)]


def test_a_running_pipeline_with_matrix_jobs_and_progress(store):
    current = run(
        9,
        109,
        status="in_progress",
        conclusion=None,
        started=8,
        updated=1,
        sha="abcdef1" + "0" * 33,
    )
    jobs = [
        job("Backend (Maven)", started=8, ended=6),
        job("Frontend (admin)", started=8, ended=7),
        job("Frontend (public)", status="in_progress", conclusion=None, started=8, ended=None),
        job("Version Check", conclusion="skipped", started=8, ended=8),
    ]
    gh = GitHub([current, run(5, 105)], {9: jobs, 5: GOOD_JOBS})

    r = collect(store, gh).repos[0].run

    assert (r.number, r.state, r.sha, r.commit, r.author, r.seconds) == (
        109,
        "running",
        "abcdef1",
        "feat: menu cards",
        "A",
        480,
    )
    assert r.usual == [600, 600]
    shown = {j.key: (j.state, j.count, j.column, j.needs) for j in r.jobs}
    assert shown == {
        "backend": ("done", 1, 0, []),
        "frontend": ("running", 2, 0, []),
        "approve": ("queued", 1, 1, ["backend", "frontend"]),
        "images": ("queued", 1, 2, ["approve"]),
        "release": ("queued", 1, 3, ["images"]),
    }
    frontend = next(j for j in r.jobs if j.key == "frontend")
    assert (frontend.name, frontend.seconds, frontend.progress) == ("Frontend", 480, 0.95)


def test_waiting_at_the_approval_gate(store):
    current = run(9, 109, status="waiting", conclusion=None, started=8, updated=3)
    jobs = [
        job("Backend (Maven)", started=8, ended=6),
        job("Frontend (admin)", started=8, ended=6),
        job("Await publish approval", status="waiting", conclusion=None, started=5, ended=None),
    ]

    r = collect(store, GitHub([current], {9: jobs})).repos[0].run

    assert r.state == "approval"
    assert r.approval_since == NOW - timedelta(minutes=5)
    assert next(j for j in r.jobs if j.key == "approve").state == "approval"


def test_a_failed_run_names_its_job_and_stays_for_ten_minutes(store):
    failed = run(9, 109, conclusion="failure", started=12, updated=4)
    jobs = [
        job("Backend (Maven)", conclusion="failure", started=12, ended=5),
        job("Frontend (admin)", started=12, ended=10),
        job("Version Check", conclusion="skipped"),
    ]
    gh = GitHub([failed], {9: jobs})

    r = collect(store, gh).repos[0].run
    assert (r.state, r.failed, r.ended_at) == (
        "failure",
        "Backend (Maven)",
        NOW - timedelta(minutes=4),
    )
    assert [j.key for j in r.jobs] == ["backend", "frontend"]  # the rest never ran: left out

    pipelines.reset()
    assert collect(store, gh, now=NOW + timedelta(minutes=7)).repos[0].run is None


def test_an_idle_repo_is_asked_once_a_minute(store):
    gh = GitHub([run(3, 103, started=300, updated=290)], {})
    collect(store, gh)
    collect(store, gh, now=NOW + timedelta(seconds=15))
    collect(store, gh, now=NOW + timedelta(seconds=61))
    assert len(gh.seen) == 2


def test_each_owner_uses_its_own_token(store):
    gh = GitHub([run(3, 103, started=300, updated=290)], {})
    collect(store, gh)
    assert gh.seen[0].headers["authorization"] == "Bearer club"
    cfg = {**CFG, "pipelines": {"repos": [{"repo": "Example/site", "workflow": "ci.yml"}]}}
    assert pipelines.settings(cfg)["repos"][0]["token"] == "mine"


def test_a_repo_github_does_not_answer_keeps_its_last_state(store):
    first = collect(store, GitHub([run(3, 103, started=300, updated=290)], {}))
    store.put_cache(pipelines.CACHE_KEY, first.model_dump(mode="json"))
    pipelines.reset()

    second = collect(store, GitHub([], {}, fail=True))

    assert second.stale is True
    assert second.repos[0].recent == first.repos[0].recent


def test_the_api_serves_the_pipelines(store):
    main.app.state.store = store
    client = TestClient(main.app)
    assert client.get("/api/pipelines").status_code == 503
    payload = collect(store, GitHub([run(3, 103, started=300, updated=290)], {}))
    store.put_cache(pipelines.CACHE_KEY, payload.model_dump(mode="json"))
    assert client.get("/api/pipelines").json()["repos"][0]["name"] == "cafe"


def test_a_run_rerun_hours_later_does_not_stretch_the_usual_range():
    assert pipelines._usual([480, 600, 26640, 520, 560]) == [480, 600]
    assert pipelines._usual([]) == []

