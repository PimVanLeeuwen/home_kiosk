from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app import desk, desk_pipelines

NOW = datetime(2026, 10, 21, 12, 30, tzinfo=UTC)
CFG = {"timezone": "Europe/Amsterdam"}


def ago(minutes: float) -> str:
    return (NOW - timedelta(minutes=minutes)).isoformat()


def recent(*minutes_ok: tuple[float, bool]) -> list[dict]:
    return [
        {"ok": ok, "seconds": round(m * 60), "at": ago(10 + i)}
        for i, (m, ok) in enumerate(reversed(minutes_ok))
    ][::-1]


JOBS = [  # home_kiosk's collector workflow, part way
    {"key": "lint", "name": "lint", "column": 0, "needs": [], "state": "done", "seconds": 21},
    {
        "key": "e2e",
        "name": "e2e",
        "column": 0,
        "needs": [],
        "state": "running",
        "seconds": 125,
        "progress": 0.62,
    },
    {
        "key": "panels",
        "name": "panels",
        "column": 0,
        "needs": [],
        "state": "running",
        "count": 1,
        "seconds": 161,
        "progress": 0.84,
    },
    {
        "key": "image",
        "name": "image",
        "column": 1,
        "needs": ["lint", "e2e", "panels"],
        "state": "queued",
    },
]


def a_run(state="running", started=4.2, ended=None, approval=None, **more) -> dict:
    return {
        "number": 312,
        "url": "https://github.com/x/y/actions/runs/1",
        "state": state,
        "started_at": ago(started),
        "ended_at": ago(ended) if ended is not None else None,
        "approval_since": ago(approval) if approval is not None else None,
        "seconds": round(started * 60) if ended is None else round((started - ended) * 60),
        "usual": [390, 420],
        "commit": "fix(panels): repeat the device key",
        "author": "Pim",
        "sha": "2a5b2c1",
        "failed": None,
        "jobs": JOBS,
        **more,
    }


def repo(name="home_kiosk", run=None, history=None) -> dict:
    return {
        "repo": f"x/{name}",
        "name": name,
        "branch": "main",
        "recent": history if history is not None else recent((6.9, True), (7.1, True)),
        "run": run,
    }


def house(store, *repos, now=NOW, stale=False):
    store.put_cache("pipelines", {"as_of": NOW.isoformat(), "stale": stale, "repos": list(repos)})
    out = desk.answer(CFG, store, "house", now)
    return out["screens"], out["rotate"]


def test_a_running_pipeline_takes_house_over(store):
    [screen], rotate = house(store, repo(run=a_run()), repo("cafe"))

    assert rotate is False
    assert {
        k: screen[k]
        for k in (
            "kind",
            "title",
            "number",
            "position",
            "state",
            "colour",
            "big",
            "first",
            "second",
            "commit",
            "meta",
            "columns",
        )
    } == {
        "kind": "pipeline",
        "title": "HOME_KIOSK · MAIN",
        "number": "RUN #312",
        "position": "",
        "state": "running",
        "colour": "#b4a9ff",
        "big": "4:12",
        "first": "about 3 min left",
        "second": "usually 6 to 7 min",
        "commit": "fix(panels): repeat the device key",
        "meta": "Pim · 2a5b2c1",
        "columns": 2,
    }
    assert screen["since"] == round((NOW - timedelta(minutes=4.2)).timestamp())


def test_the_graph_comes_as_cards_in_columns_with_edges_by_index(store):
    [screen], _ = house(store, repo(run=a_run()))
    cards = [
        (c["name"], c["column"], c["row"], c["state"], c["time"], c["progress"])
        for c in screen["jobs"]
    ]
    assert cards == [
        ("lint", 0, 0, "done", "0:21", 0),
        ("e2e", 0, 1, "running", "2:05", 620),
        ("panels", 0, 2, "running", "2:41", 840),
        ("image", 1, 0, "queued", "", 0),
    ]
    assert screen["edges"] == [[0, 3], [1, 3], [2, 3]]


def test_a_run_slower_than_usual_says_so(store):
    [screen], _ = house(store, repo(run=a_run(started=7.5)))
    assert screen["first"] == "longer than usual"


def test_a_finished_run_stays_five_minutes_then_house_turns_again(store):
    done = repo(run=a_run("success", started=11.2, ended=4))
    [screen], rotate = house(store, done)
    assert (screen["state"], screen["first"], screen["big"], screen["since"], rotate) == (
        "success",
        "Shipped",
        "7:12",
        0,
        False,
    )

    [screen, *_rest], rotate = house(store, done, now=NOW + timedelta(minutes=2))
    assert (screen["kind"], rotate) == ("pipelines", True)


def test_a_failed_run_names_its_job(store):
    failed = repo(run=a_run("failure", started=6, ended=1, failed="e2e"))
    [screen], _ = house(store, failed)
    assert (screen["colour"], screen["first"], screen["second"]) == ("#e5646a", "Failed", "e2e")


def test_an_approval_gate_holds_five_minutes_then_waits_on_the_idle_card(store):
    gate = repo("cafe", run=a_run("approval", started=12, approval=3))
    [screen], rotate = house(store, gate)
    assert (screen["first"], screen["second"], screen["colour"], rotate) == (
        "Waiting for approval",
        "waiting 3 min",
        "#e0a23b",
        False,
    )

    [card, *_rest], rotate = house(store, gate, now=NOW + timedelta(minutes=3))
    assert rotate is True
    assert card["repos"][0]["line"] == "main · waiting for approval"


def test_two_pipelines_take_turns(store):
    screens, rotate = house(store, repo("cafe", run=a_run(started=2)), repo(run=a_run(started=4.2)))
    assert rotate is True
    assert [(s["title"], s["position"]) for s in screens] == [
        ("HOME_KIOSK · MAIN", "1 of 2"),
        ("CAFE · MAIN", "2 of 2"),
    ]


def test_the_idle_card_has_each_repos_last_result_and_bars(store):
    history = recent((6.9, True), (4.2, False), (7.0, True), (443.6, True))
    [card, *_rest], rotate = house(store, repo(history=history), repo("cafe", history=[]))

    assert rotate is True
    assert (card["kind"], card["title"], card["right"]) == (
        "pipelines",
        "PIPELINES",
        "LAST 10 RUNS ON MAIN",
    )
    first, second = card["repos"]
    assert (first["name"], first["line"], first["colour"]) == (
        "home_kiosk",
        "main · passed 10 min ago",
        "#3fb97f",
    )
    assert [b["height"] for b in first["bars"]] == [493, 300, 500, 1000]  # 443 min capped at 14 min
    assert [b["ok"] for b in first["bars"]] == [True, False, True, True]
    assert second["line"] == "main · no runs yet" and second["bars"] == []


def test_before_any_pipeline_data_the_card_waits(store):
    out = desk.answer(CFG, store, "house", NOW)
    assert out["screens"] == [{"kind": "pipelines", "stale": False, "present": False},
        {"kind": "code", "stale": False, "present": False},
        {"kind": "sites", "stale": False, "present": False},
        {"kind": "services", "stale": False, "present": False},
        {"kind": "tailnet", "stale": False, "present": False},
        {"kind": "movers", "stale": False, "present": False}]


def test_times_and_ages_read_well():
    assert [desk_pipelines.clock(s) for s in (0, 59, 411, 3723)] == [
        "0:00",
        "0:59",
        "6:51",
        "1:02:03",
    ]
    assert [
        desk_pipelines.ago(NOW - timedelta(minutes=m), NOW) for m in (0.2, 12, 125, 1500, 4000)
    ] == ["1 min ago", "12 min ago", "2 h ago", "yesterday", "3 days ago"]
