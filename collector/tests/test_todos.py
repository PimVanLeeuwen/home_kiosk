from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from app import main, todos
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
