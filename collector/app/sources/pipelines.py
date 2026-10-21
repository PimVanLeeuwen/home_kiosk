"""The House panel's pipelines (plan.md M21): the main CI workflow of a few repos,
only when a push to the default branch started it.

Every 15 s each repo's latest runs of that workflow are read (once a minute while
nothing runs). The latest run, while it runs and for a while after, gets its jobs
and the workflow file at its commit: the jobs API has no edges, the file's `needs`
has. A matrix job is one card with a count and a combined state, skipped jobs are
left out, and a job waiting at an environment's approval is an approval gate.
Read-only, with the Repos page's tokens (Actions: read).
"""

from __future__ import annotations

import logging
import re
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import yaml

from ..models import JobState, PipelineJob, PipelineRecent, PipelineRepo, PipelineRun, Pipelines
from ..store import Store

log = logging.getLogger(__name__)

CACHE_KEY = "pipelines"
API = "https://api.github.com"
TIMEOUT_SECONDS = 20
IDLE_EVERY = timedelta(seconds=60)  # how often a repo with nothing running is asked
SHOWN_AFTER = timedelta(minutes=10)  # a finished run stays in the payload this long
RECENT = 10  # finished runs for the bars
USUAL_FROM = 5  # good runs that make "usually 6 to 7 min"

ACTIVE = {"queued", "in_progress", "waiting", "requested", "pending"}
_TEMPLATE = re.compile(r"\$\{\{.*?\}\}")

# Kept between runs: the workflow graph per commit, the job lengths of each repo's
# last good run, and the last answer per repo (for the once-a-minute idle reads).
_graphs: dict[tuple[str, str], dict[str, dict[str, Any]]] = {}
_lengths: dict[str, tuple[int, dict[str, int]]] = {}
_last: dict[str, tuple[datetime, list[dict[str, Any]], bool]] = {}


def reset() -> None:
    """Forget what is kept between runs (tests)."""
    _graphs.clear(), _lengths.clear(), _last.clear()


def settings(cfg: dict[str, Any]) -> dict[str, Any]:
    p = cfg.get("pipelines") or {}
    gh = cfg.get("github") or {}
    tokens = {o["login"]: (o.get("token") or "").strip() for o in gh.get("owners") or []}
    default = (gh.get("token") or "").strip()
    repos = []
    for r in p.get("repos") or []:
        owner, _, name = str(r["repo"]).partition("/")
        repos.append({"repo": r["repo"], "workflow": r["workflow"],
                      "branch": r.get("branch", "main"), "name": r.get("name") or name,
                      "token": tokens.get(owner) or default})
    return {"repos": repos, "enabled": bool(repos)}


def _time(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value.replace("Z", "+00:00")) if value else None


def parse_workflow(text: str) -> dict[str, dict[str, Any]]:
    """Each job of a workflow file: its name template and what it needs, in order."""
    jobs = (yaml.safe_load(text) or {}).get("jobs") or {}
    out = {}
    for key, job in jobs.items():
        needs = (job or {}).get("needs") or []
        out[str(key)] = {"name": str((job or {}).get("name") or key),
                         "needs": [needs] if isinstance(needs, str) else [str(n) for n in needs]}
    return out


def columns(graph: dict[str, dict[str, Any]]) -> dict[str, int]:
    """A job's stage: 0 when it needs nothing, else one more than the latest it needs."""
    depth: dict[str, int] = {}

    def of(key: str, seen: tuple[str, ...] = ()) -> int:
        if key not in depth:
            needs = [n for n in graph[key]["needs"] if n in graph and n not in seen]
            depth[key] = 1 + max((of(n, (*seen, key)) for n in needs), default=-1)
        return depth[key]

    for key in graph:
        of(key)
    return depth


def display(template: str) -> str:
    """A short name for a card: "Build & push (${{ matrix.service }})" as "Build & push",
    and "E2E (Playwright · full stack)" as "E2E" (a trailing part in brackets goes)."""
    name = _TEMPLATE.sub("", template)
    name = re.sub(r"\s*\([^()]*\)\s*$", "", name).strip()
    return name or template


def _matcher(template: str) -> re.Pattern[str]:
    parts = _TEMPLATE.split(template)
    return re.compile(".+".join(re.escape(p) for p in parts) + r"\Z")


def _key_of(name: str, graph: dict[str, dict[str, Any]]) -> str | None:
    for key, job in graph.items():
        if name == key or _matcher(job["name"]).match(name):
            return key
    return None


def _state(jobs: list[dict[str, Any]], run_done: bool) -> JobState | None:
    """The combined state of a job's runs (several for a matrix); None when skipped."""
    if not jobs:
        return None if run_done else "queued"
    conclusions = {j.get("conclusion") for j in jobs}
    statuses = {j.get("status") for j in jobs}
    if conclusions & {"failure", "timed_out", "startup_failure"}:
        return "failed"
    if "waiting" in statuses:
        return "approval"
    if "in_progress" in statuses or (statuses & ACTIVE and "completed" in statuses):
        return "running"
    if statuses & ACTIVE:
        return "queued"
    if conclusions <= {"skipped"}:
        return None
    if "cancelled" in conclusions:
        return "cancelled"
    return "done"


def _seconds(jobs: list[dict[str, Any]], now: datetime) -> int | None:
    starts = [t for j in jobs if (t := _time(j.get("started_at")))]
    if not starts:
        return None
    ends = [_time(j.get("completed_at")) for j in jobs]
    end = max(e for e in ends if e) if all(ends) else now
    return max(0, round((end - min(starts)).total_seconds()))


def build_jobs(graph: dict[str, dict[str, Any]], runtime: list[dict[str, Any]], run_done: bool,
               lengths: dict[str, int], now: datetime) -> list[PipelineJob]:
    by_key: dict[str, list[dict[str, Any]]] = {key: [] for key in graph}
    for job in runtime:
        key = _key_of(job.get("name") or "", graph)
        if key:
            by_key[key].append(job)
    depth = columns(graph)
    out = []
    for key, job in graph.items():
        state = _state(by_key[key], run_done)
        if state is None:
            continue
        seconds = _seconds(by_key[key], now)
        progress = None
        if state == "running" and seconds is not None and lengths.get(key):
            progress = round(min(0.95, seconds / lengths[key]), 2)
        out.append(PipelineJob(key=key, name=display(job["name"]), column=depth[key],
                               needs=[n for n in job["needs"] if n in graph], state=state,
                               count=max(1, len(by_key[key])), seconds=seconds, progress=progress))
    shown = {j.key for j in out}
    for j in out:  # an edge to a skipped job goes nowhere
        j.needs = [n for n in j.needs if n in shown]
    return out


class Client:
    def __init__(self, http: httpx.AsyncClient, token: str):
        self.http, self.headers = http, {
            "Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28"}

    async def json(self, path: str, **params: Any) -> dict[str, Any]:
        resp = await self.http.get(f"{API}{path}", params=params, headers=self.headers)
        resp.raise_for_status()
        return resp.json()

    async def raw(self, path: str, **params: Any) -> str:
        headers = {**self.headers, "Accept": "application/vnd.github.raw+json"}
        resp = await self.http.get(f"{API}{path}", params=params, headers=headers)
        resp.raise_for_status()
        return resp.text


async def _graph(client: Client, repo: str, run: dict[str, Any]) -> dict[str, dict[str, Any]]:
    key = (repo, run["head_sha"])
    if key not in _graphs:
        _graphs[key] = parse_workflow(await client.raw(f"/repos/{repo}/contents/{run['path']}",
                                                       ref=run["head_sha"]))
    return _graphs[key]


async def _job_lengths(client: Client, repo: str, graph: dict[str, dict[str, Any]],
                       good: dict[str, Any] | None) -> dict[str, int]:
    """Each job's length in the last good run, for the progress lines."""
    if good is None:
        return {}
    if _lengths.get(repo, (None,))[0] != good["id"]:
        path = f"/repos/{repo}/actions/runs/{good['id']}/jobs"
        jobs = (await client.json(path, per_page=100))["jobs"]
        by_key: dict[str, list[dict[str, Any]]] = {}
        for job in jobs:
            if (k := _key_of(job.get("name") or "", graph)):
                by_key.setdefault(k, []).append(job)
        end = _time(good["updated_at"])
        _lengths[repo] = (good["id"], {k: s for k, js in by_key.items()
                                       if (s := _seconds(js, end)) is not None})
    return _lengths[repo][1]


def _duration(run: dict[str, Any], now: datetime) -> int:
    start = _time(run.get("run_started_at") or run["created_at"])
    end = _time(run["updated_at"]) if run["status"] == "completed" else now
    return max(0, round((end - start).total_seconds()))


def _usual(seconds: list[int]) -> list[int]:
    """The shortest and longest of the last good runs, leaving out any that took more
    than twice the median (a run re-run hours later)."""
    if not seconds:
        return []
    ordered = sorted(seconds)
    median = ordered[len(ordered) // 2]
    kept = [s for s in ordered if s <= 2 * median]
    return [kept[0], kept[-1]]


async def _current(client: Client, repo: str, run: dict[str, Any], runs: list[dict[str, Any]],
                   now: datetime) -> PipelineRun:
    graph = await _graph(client, repo, run)
    done = run["status"] == "completed"
    runtime = (await client.json(f"/repos/{repo}/actions/runs/{run['id']}/jobs", per_page=100,
                                 filter="latest"))["jobs"]
    good = [r for r in runs if r["status"] == "completed" and r["conclusion"] == "success"
            and r["id"] != run["id"]]
    lengths = await _job_lengths(client, repo, graph, good[0] if good else None)
    jobs = build_jobs(graph, runtime, done, lengths, now)
    gates = [j for j in jobs if j.state == "approval"]
    if done:
        state = run["conclusion"] if run["conclusion"] in ("success", "cancelled") else "failure"
    else:
        state = "approval" if gates else "running"
    waiting = [t for j in runtime
               if j.get("status") == "waiting" and (t := _time(j.get("started_at")))]
    usual = _usual([_duration(r, now) for r in good[:USUAL_FROM]])
    commit = (run.get("head_commit") or {})
    return PipelineRun(
        number=run["run_number"], url=run["html_url"], state=state,
        started_at=_time(run.get("run_started_at") or run["created_at"]),
        ended_at=_time(run["updated_at"]) if done else None,
        approval_since=min(waiting) if waiting and state == "approval" else None,
        seconds=_duration(run, now), usual=usual,
        commit=(commit.get("message") or "").split("\n")[0][:120],
        author=(commit.get("author") or {}).get("name"), sha=run["head_sha"][:7],
        failed=next((j.name for j in jobs if j.state == "failed"), None), jobs=jobs)


async def repo_state(client: Client, r: dict[str, Any], now: datetime) -> PipelineRepo:
    repo = r["repo"]
    last = _last.get(repo)
    if last and not last[2] and now - last[0] < IDLE_EVERY:
        runs = last[1]
    else:
        runs = (await client.json(f"/repos/{repo}/actions/workflows/{r['workflow']}/runs",
                                  branch=r["branch"], event="push", per_page=15))["workflow_runs"]
    latest = runs[0] if runs else None
    active = bool(latest) and (latest["status"] in ACTIVE
                               or now - _time(latest["updated_at"]) <= SHOWN_AFTER)
    _last[repo] = (now if not (last and runs is last[1]) else last[0], runs, active)
    finished = [x for x in runs if x["status"] == "completed" and x["conclusion"] != "skipped"]
    recent = [PipelineRecent(ok=x["conclusion"] == "success", seconds=_duration(x, now),
                             at=_time(x["updated_at"])) for x in finished[:RECENT]][::-1]
    run = await _current(client, repo, latest, runs, now) if active else None
    return PipelineRepo(repo=repo, name=r["name"], branch=r["branch"], recent=recent, run=run)


async def collect(cfg: dict[str, Any], store: Store,
                  transport: httpx.AsyncBaseTransport | None = None,
                  now: datetime | None = None) -> Pipelines:
    """`transport` and `now` are for tests. A repo GitHub does not answer keeps
    its last known state, and the payload is marked stale."""
    now = now or datetime.now(UTC)
    previous = {r["repo"]: r for r in (store.get_cache(CACHE_KEY) or {}).get("repos") or []}
    repos, stale = [], False
    async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS, transport=transport) as http:
        for r in settings(cfg)["repos"]:
            try:
                repos.append(await repo_state(Client(http, r["token"]), r, now))
            except Exception as exc:
                log.warning("pipelines for %s failed: %s", r["repo"], type(exc).__name__)
                stale = True
                if r["repo"] in previous:
                    repos.append(PipelineRepo.model_validate(previous[r["repo"]]))
    return Pipelines(as_of=now, stale=stale, repos=repos)
