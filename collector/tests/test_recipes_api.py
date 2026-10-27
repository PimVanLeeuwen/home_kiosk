"""The Recipes endpoints (plan.md M30): paste, check, replace, undo, Copy all."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app import main
from app.recipes import store as recipes

from .test_recipes import shoarma

JSON = {"Content-Type": "application/json"}


@pytest.fixture
def client(store):
    recipes.ensure_tables(store)
    main.app.state.store = store
    main.app.state.config = {}
    return TestClient(main.app)


def renamed(title: str, rid: str) -> dict:
    return shoarma() | {"title": title, "id": rid}


def test_pasting_adds_recipes_and_lists_them(client):
    paste = {"data": [shoarma(), renamed("Dal met spinazie", "dal") | {"tags": ["vega"]}]}
    assert client.post("/api/recipes/check", json=paste).json()["recipes"] == [
        {"id": "kip-shoarma-uit-de-oven", "title": "Kip shoarma uit de oven", "result": "new",
         "changes": []},
        {"id": "dal", "title": "Dal met spinazie", "result": "new", "changes": []}]
    saved = client.post("/api/recipes/import", json=paste).json()["saved"]
    assert [s["result"] for s in saved] == ["added", "added"]

    body = client.get("/api/recipes").json()
    assert body["count"] == 2 and body["stale"] is False
    assert [r["title"] for r in body["recipes"]] == ["Dal met spinazie", "Kip shoarma uit de oven"]
    assert body["tags"][:2] == [{"tag": "doordeweeks", "count": 1}, {"tag": "oven", "count": 1}]
    assert client.get("/api/recipes/dal").json()["recipe"]["tags"] == ["vega"]


def test_a_faulty_paste_saves_nothing(client):
    bad = renamed("Dal", "dal") | {"servings": "4"}
    check = client.post("/api/recipes/check", json={"data": [shoarma(), bad]}).json()
    assert check["ok"] is False
    assert check["problems"] == [{"path": "[1].servings",
                                  "message": "is text; it should be a number, like 2"}]
    answer = client.post("/api/recipes/import", json={"data": [shoarma(), bad]})
    assert answer.status_code == 422
    assert client.get("/api/recipes").json()["count"] == 0


def test_a_paste_that_is_not_recipes_is_refused(client):
    check = client.post("/api/recipes/check", json={"data": "hello"}).json()
    assert check["problems"][0]["path"] == "(the paste)"
    twice = client.post("/api/recipes/check", json={"data": [shoarma(), shoarma()]}).json()
    assert twice["problems"] == [{"path": "id",
                                  "message": '"kip-shoarma-uit-de-oven" is in the paste 2 times'}]


def test_replacing_needs_a_yes_after_the_check(client):
    client.post("/api/recipes/import", json={"data": shoarma()})
    changed = shoarma() | {"servings": 4}
    check = client.post("/api/recipes/check", json={"data": changed}).json()
    assert check["recipes"][0]["result"] == "replace"
    assert check["recipes"][0]["changes"] == [{"kind": "changed",
                                               "text": "Servings: 4 instead of 2"}]
    refused = client.post("/api/recipes/import", json={"data": changed})
    assert refused.status_code == 409
    assert refused.json()["detail"]["ids"] == ["kip-shoarma-uit-de-oven"]
    ok = client.post("/api/recipes/import", json={"data": changed, "replace": True})
    assert ok.json()["saved"][0]["result"] == "replaced"
    same = client.post("/api/recipes/check", json={"data": changed}).json()
    assert same["recipes"][0]["result"] == "same"


def test_put_replaces_only_its_own_recipe_and_undo_puts_it_back(client):
    rid = "kip-shoarma-uit-de-oven"
    client.post("/api/recipes/import", json={"data": shoarma()})
    wrong = client.put(f"/api/recipes/{rid}", json=renamed("Dal", "dal"))
    assert wrong.status_code == 422
    assert wrong.json()["detail"]["problems"][0]["message"] == f'is "dal"; this recipe is "{rid}"'

    put = client.put(f"/api/recipes/{rid}", json=shoarma() | {"title": "Shoarma"}).json()
    assert put["result"] == "replaced" and put["previous_at"]
    assert client.post(f"/api/recipes/{rid}/undo", headers=JSON).json()["recipe"]["title"] == (
        "Kip shoarma uit de oven")
    assert client.post(f"/api/recipes/{rid}/undo", headers=JSON).status_code == 409

    assert client.delete(f"/api/recipes/{rid}").json() == {"deleted": rid}
    assert client.get(f"/api/recipes/{rid}").status_code == 404


def test_export_carries_the_guide_the_schema_and_every_recipe(client):
    client.post("/api/recipes/import", json={"data": shoarma()})
    export = client.get("/api/recipes/export").json()
    assert export["schema"] == "hub-recipe/1"
    assert "prep" in export["guide"]
    assert "phases" in export["json_schema"]["properties"]
    assert export["recipes"][0]["id"] == "kip-shoarma-uit-de-oven"
    # Copy all's JSON pasted back as is changes nothing.
    again = client.post("/api/recipes/check", json={"data": export}).json()
    assert again["recipes"][0]["result"] == "same"


def test_writes_need_the_hubs_own_origin(client):
    other = client.post("/api/recipes/import", json={"data": shoarma()},
                        headers={"Origin": "https://evil.example"})
    assert other.status_code == 403
    assert client.delete("/api/recipes/x", headers={"Origin": "https://evil.example"}
                         ).status_code == 403
