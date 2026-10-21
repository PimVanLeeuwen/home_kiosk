"""The House panel's pipelines (plan.md M21), ready to draw.

While a watched repo's main CI runs, House shows its job graph and stops turning;
a finished run stays for 5 minutes (green or red), and so does a run that reaches
an approval gate, after which House turns again with the gate on the idle card.
Two runs at once take turns ("1 of 2"). Otherwise the idle card is one of House's
screens: each repo's last result and its last runs as bars.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from .panel_text import latin1
from .sources import pipelines
from .store import Store

SHOWN_FOR = timedelta(minutes=5)  # a finished run, or one waiting at a gate

TONE = {"running": "#b4a9ff", "approval": "#e0a23b", "success": "#3fb97f",
        "failure": "#e5646a", "cancelled": "#8a8794"}


def clock(seconds: int) -> str:
    """6:51, or 1:02:03 past an hour."""
    h, rest = divmod(max(0, seconds), 3600)
    m, s = divmod(rest, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def _minutes(seconds: int) -> int:
    return max(1, round(seconds / 60))


def ago(at: datetime, now: datetime) -> str:
    seconds = (now - at).total_seconds()
    if seconds < 3600:
        return f"{max(1, round(seconds / 60))} min ago"
    if seconds < 86400:
        return f"{round(seconds / 3600)} h ago"
    days = round(seconds / 86400)
    return "yesterday" if days == 1 else f"{days} days ago"


def _time(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None


def showing(run: dict[str, Any] | None, now: datetime) -> bool:
    """Whether this run takes House over now."""
    if not run:
        return False
    if run["state"] == "running":
        return True
    if run["state"] == "approval":
        since = _time(run.get("approval_since"))
        return since is None or now - since <= SHOWN_FOR
    ended = _time(run.get("ended_at"))
    return ended is not None and now - ended <= SHOWN_FOR


def _layout(jobs: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[list[int]], int]:
    """Cards in stage columns, rows in the workflow's order, and edges by card index."""
    order = sorted(range(len(jobs)), key=lambda i: (jobs[i]["column"], i))
    rows: dict[int, int] = {}
    cards, index = [], {}
    for i in order:
        j = jobs[i]
        row = rows.get(j["column"], 0)
        rows[j["column"]] = row + 1
        index[j["key"]] = len(cards)
        cards.append({"name": latin1(j["name"]), "column": j["column"], "row": row,
                      "count": j.get("count", 1), "state": j["state"],
                      "time": clock(j["seconds"]) if j.get("seconds") is not None else "",
                      "progress": round((j.get("progress") or 0) * 1000)})
    edges = [[index[n], index[j["key"]]] for j in jobs for n in j.get("needs") or [] if n in index]
    return cards, edges, max(rows) + 1 if rows else 0


def _lines(run: dict[str, Any], now: datetime) -> tuple[str, str, str]:
    """The big time and the two lines beside it."""
    usual = run.get("usual") or []
    usual_line = (f"usually {_minutes(usual[0])} to {_minutes(usual[1])} min"
                  if usual and _minutes(usual[0]) != _minutes(usual[1])
                  else f"usually {_minutes(usual[0])} min" if usual else "")
    seconds = run["seconds"]
    if run["state"] == "running":
        if usual:
            left = (usual[0] + usual[1]) / 2 - seconds
            first = f"about {_minutes(left)} min left" if left > 30 else "longer than usual"
        else:
            first = "running"
        return clock(seconds), first, usual_line
    if run["state"] == "approval":
        since = _time(run.get("approval_since")) or now
        waited = _minutes((now - since).total_seconds())
        return clock(seconds), "Waiting for approval", f"waiting {waited} min"
    if run["state"] == "success":
        return clock(seconds), "Shipped", usual_line
    if run["state"] == "failure":
        return clock(seconds), "Failed", latin1(run.get("failed") or "")
    return clock(seconds), "Cancelled", ""


def pipeline_screen(repo: dict[str, Any], now: datetime, position: str = "",
                    stale: bool = False) -> dict[str, Any]:
    run = repo["run"]
    cards, edges, cols = _layout(run.get("jobs") or [])
    big, first, second = _lines(run, now)
    started = _time(run.get("started_at"))
    return {
        "kind": "pipeline", "stale": stale, "present": True,
        "title": latin1(f"{repo['name']} · {repo['branch']}").upper(),
        "number": f"RUN #{run['number']}", "position": position,
        "state": run["state"], "colour": TONE[run["state"]],
        "big": big,
        # While it runs the panel counts the time on from here, seconds since 1970.
        "since": round(started.timestamp()) if run["state"] == "running" and started else 0,
        "first": first, "second": second,
        "commit": latin1(run.get("commit") or ""),
        "meta": latin1(" · ".join(p for p in (run.get("author"), run.get("sha")) if p)),
        "columns": cols, "jobs": cards, "edges": edges,
    }


def _bars(recent: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Each finished run as a bar, 0 to 1000 high by its length; a run more than
    twice the median (re-run hours later) is capped there."""
    if not recent:
        return []
    seconds = sorted(r["seconds"] for r in recent)
    cap = 2 * seconds[len(seconds) // 2] or 1
    top = max(min(r["seconds"], cap) for r in recent) or 1
    return [{"height": round(min(r["seconds"], cap) / top * 1000), "ok": r["ok"]} for r in recent]


def _repo_line(repo: dict[str, Any], now: datetime) -> tuple[str, str]:
    run = repo.get("run")
    if run and run["state"] == "approval":
        return f"{repo['branch']} · waiting for approval", TONE["approval"]
    if run and run["state"] == "running":
        return f"{repo['branch']} · running", TONE["running"]
    recent = repo.get("recent") or []
    if not recent:
        return f"{repo['branch']} · no runs yet", TONE["cancelled"]
    last = recent[-1]
    word = "passed" if last["ok"] else "failed"
    return (f"{repo['branch']} · {word} {ago(_time(last['at']), now)}",
            TONE["success"] if last["ok"] else TONE["failure"])


def idle_screen(cached: dict[str, Any], now: datetime) -> dict[str, Any]:
    repos = []
    for repo in cached.get("repos") or []:
        line, colour = _repo_line(repo, now)
        repos.append({"name": latin1(repo["name"]), "line": latin1(line), "colour": colour,
                      "bars": _bars(repo.get("recent") or [])})
    return {"kind": "pipelines", "stale": bool(cached.get("stale")), "present": bool(repos),
            "title": "PIPELINES", "right": f"LAST {pipelines.RECENT} RUNS ON MAIN", "repos": repos}


Screens = list[dict[str, Any]]


def house_pipelines(store: Store, zone: ZoneInfo, now: datetime) -> tuple[Screens, bool]:
    """House's pipeline screens and whether House turns: the running (or just finished)
    pipelines alone, taking turns when there are two; otherwise the idle card."""
    cached = store.get_cache(pipelines.CACHE_KEY)
    if not cached:
        return [{"kind": "pipelines", "stale": False, "present": False}], True
    stale = bool(cached.get("stale"))
    live = [r for r in cached.get("repos") or [] if showing(r.get("run"), now)]
    if live:
        live.sort(key=lambda r: r["run"]["started_at"])
        n = len(live)
        return ([pipeline_screen(r, now, f"{i + 1} of {n}" if n > 1 else "", stale)
                 for i, r in enumerate(live)], n > 1)
    return [idle_screen(cached, now)], True
