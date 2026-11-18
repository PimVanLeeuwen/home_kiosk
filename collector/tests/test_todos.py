from __future__ import annotations

import asyncio
from datetime import UTC, date, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from app import main, todos
from app.alerts import core, page
from app.todos import Draft

CFG = {"timezone": "Europe/Amsterdam"}
TUE = date(2026, 11, 3)
NOW = datetime(2026, 11, 3, 9, 0, tzinfo=UTC)


@pytest.fixture
def todo_store(store):
    todos.ensure_tables(store)
    return store


def titles(store) -> list[str]:
    return [t.title for t in todos.all_todos(store)]


def test_high_first_then_by_due_date_then_oldest(todo_store):
    add = lambda title, minutes, **kw: todos.add(  # noqa: E731
        todo_store, Draft(title=title, **kw), NOW + timedelta(minutes=minutes))
    add("no date, old", 0)
    add("no date, new", 5)
    add("due later", 1, due=TUE + timedelta(days=3))
    add("due sooner", 2, due=TUE)
    add("high, no date", 3, high=True)
    add("high, due", 4, high=True, due=TUE + timedelta(days=9))
    assert titles(todo_store) == ["high, due", "high, no date", "due sooner", "due later",
                                  "no date, old", "no date, new"]


def test_a_due_date_marks_overdue_and_today():
    assert todos.state(Draft(title="a", due=TUE - timedelta(days=1)), TUE) == "overdue"
    assert todos.state(Draft(title="a", due=TUE), TUE) == "today"
    assert todos.state(Draft(title="a", due=TUE + timedelta(days=1)), TUE) is None
    assert todos.state(Draft(title="a"), TUE) is None


def test_the_overview_counts_what_is_open(todo_store):
    todos.add(todo_store, Draft(title="Tax return", due=TUE - timedelta(days=2)))
    todos.add(todo_store, Draft(title="Ring the plumber", due=TUE))
    todos.add(todo_store, Draft(title="Fix the shed", note="hinge on the left door"))
    seen = todos.overview(todo_store, NOW, TUE)
    assert (seen["open"], seen["overdue"], seen["due_today"]) == (3, 1, 1)
    assert [(t["title"], t["state"]) for t in seen["todos"]] == [
        ("Tax return", "overdue"), ("Ring the plumber", "today"), ("Fix the shed", None)]
    assert seen["todos"][2]["note"] == "hinge on the left door"


def test_a_blank_note_is_no_note_and_a_title_is_needed():
    assert Draft(title=" Bins ", note="   ").model_dump()["note"] is None
    assert Draft(title=" Bins ").title == "Bins"
    with pytest.raises(ValueError):
        Draft(title="  ")
    with pytest.raises(ValueError):
        Draft(title="a", note="x" * 501)


def test_undo_puts_a_ticked_todo_back_where_it_was(todo_store):
    first = todos.add(todo_store, Draft(title="first"), NOW)
    todos.add(todo_store, Draft(title="second"), NOW + timedelta(minutes=1))
    removed = todos.remove(todo_store, first.id)
    assert removed == first
    assert titles(todo_store) == ["second"]
    assert todos.restore(todo_store, removed)
    assert titles(todo_store) == ["first", "second"]
    assert todos.get(todo_store, first.id) == first
    assert not todos.restore(todo_store, removed)  # already back
    assert todos.remove(todo_store, 999) is None


@pytest.fixture
def client(todo_store):
    main.app.state.store = todo_store
    main.app.state.config = CFG
    return TestClient(main.app, headers={"origin": "http://testserver"})


def test_the_page_adds_changes_ticks_off_and_undoes(client):
    body = {"title": "Tax return", "note": "the box 3 part", "due": "2026-11-20", "high": True}
    [made] = client.post("/api/todos", json=body).json()["todos"]
    assert (made["title"], made["note"], made["due"], made["high"]) == (
        "Tax return", "the box 3 part", "2026-11-20", True)

    changed = client.put(f"/api/todos/{made['id']}", json=body | {"high": False})
    assert changed.json()["todos"][0]["high"] is False
    assert client.put("/api/todos/999", json=body).status_code == 404

    ticked = client.delete(f"/api/todos/{made['id']}").json()
    assert ticked["todos"] == [] and ticked["open"] == 0
    assert ticked["removed"]["id"] == made["id"]
    assert client.delete(f"/api/todos/{made['id']}").status_code == 404

    back = client.post("/api/todos/restore", json=ticked["removed"]).json()
    assert back["todos"][0]["id"] == made["id"]
    assert client.post("/api/todos/restore", json=ticked["removed"]).status_code == 409


def test_the_page_checks_what_it_is_sent(client):
    assert client.post("/api/todos", json={"title": "  "}).status_code == 422
    assert client.post("/api/todos", json={"title": "a", "due": "someday"}).status_code == 422
    assert client.post("/api/todos", json={"title": "a", "note": "x" * 501}).status_code == 422
    other = TestClient(main.app, headers={"origin": "http://evil.example"})
    assert other.post("/api/todos", json={"title": "a"}).status_code == 403
    assert other.delete("/api/todos/1").status_code == 403


def test_at_most_so_many_open_todos(client, monkeypatch):
    monkeypatch.setattr(todos, "MAX_OPEN", 1)
    assert client.post("/api/todos", json={"title": "one"}).status_code == 200
    assert client.post("/api/todos", json={"title": "two"}).status_code == 422


# --- the daily message ----------------------------------------------------------------


def test_the_message_counts_them_and_lists_the_first_five():
    day = TUE
    listed = [todos.Todo(id=1, title="Tax return", due=day - timedelta(days=3), high=True,
                         created=NOW),
              todos.Todo(id=2, title="Plumber", due=day, created=NOW),
              todos.Todo(id=3, title="Shed", due=day - timedelta(days=1), created=NOW)]
    listed += [todos.Todo(id=i, title=f"Todo {i}", created=NOW) for i in range(4, 8)]
    title, body = todos.message(listed, day)
    assert title == "7 open todos, 2 overdue"
    assert body.split("\n") == ["High: Tax return (3 days late)", "Plumber (today)",
                                "Shed (yesterday)", "Todo 4", "Todo 5", "and 2 more"]
    assert todos.message(listed[3:4], day) == ("1 open todo", "Todo 4")


def test_the_message_goes_out_once_a_day_at_the_set_time(todo_store, monkeypatch):
    sent = []

    async def notify(store, cfg, **kw):
        sent.append((kw["category"], kw["title"]))

    monkeypatch.setattr(core, "notify", notify)
    todos.add(todo_store, Draft(title="Fix the shed"))
    run = lambda now: asyncio.run(todos.send_daily(CFG, todo_store, now))  # noqa: E731

    assert not run(datetime(2026, 11, 3, 6, 59, tzinfo=UTC))  # 07:59 in Amsterdam
    assert run(datetime(2026, 11, 3, 7, 0, tzinfo=UTC))
    assert not run(datetime(2026, 11, 3, 7, 1, tzinfo=UTC))  # already sent today
    assert sent == [("todos", "1 open todo")]
    assert run(datetime(2026, 11, 8, 7, 0, tzinfo=UTC))  # a Sunday too

    todos.put_message_at(todo_store, "18:30")
    assert not run(datetime(2026, 11, 9, 7, 0, tzinfo=UTC))
    assert run(datetime(2026, 11, 9, 17, 30, tzinfo=UTC))


def test_no_message_with_nothing_open_or_hours_late(todo_store, monkeypatch):
    sent = []
    monkeypatch.setattr(core, "notify", lambda *a, **k: sent.append(k) or asyncio.sleep(0))
    run = lambda now: asyncio.run(todos.send_daily(CFG, todo_store, now))  # noqa: E731

    assert not run(datetime(2026, 11, 3, 7, 0, tzinfo=UTC))  # nothing open
    todos.add(todo_store, Draft(title="Fix the shed"))
    assert not run(datetime(2026, 11, 3, 7, 5, tzinfo=UTC))  # that day is done
    assert not run(datetime(2026, 11, 4, 9, 1, tzinfo=UTC))  # 10:01, over two hours late
    assert sent == []


def test_settings_keep_the_time_and_the_message_links_to_the_page(client):
    assert client.get("/api/settings/todos").json() == {"at": "08:00"}
    assert client.put("/api/settings/todos", json={"at": "07:15"}).json() == {"at": "07:15"}
    assert client.get("/api/settings/todos").json() == {"at": "07:15"}
    assert client.put("/api/settings/todos", json={"at": "7:15"}).status_code == 422
    assert client.put("/api/settings/todos", json={"at": "24:00"}).status_code == 422
    other = TestClient(main.app, headers={"origin": "http://evil.example"})
    assert other.put("/api/settings/todos", json={"at": "07:15"}).status_code == 403
    assert {"label": "Todos page", "page": "/todos", "hint": ""} in page.links(
        {"source": "todos", "category": "todos"})
