"""The Tandoor import and recipe photos (plan.md M30, step 2). The export here is made up."""

from __future__ import annotations

import io
import json
import zipfile

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app import main
from app.recipes import photos, tandoor
from app.recipes import store as recipes

from .test_recipes import shoarma


def food(name, amount, unit=None, category=None, **more):
    return {"food": {"name": name, "supermarket_category": category and {"name": category}},
            "unit": unit and {"name": unit}, "amount": amount, "note": "", "is_header": False,
            "no_amount": False, **more}


def tandoor_recipe(name="Kip shoarma uit de oven") -> dict:
    return {
        "name": name, "description": "", "servings": 2, "servings_text": "porties",
        "working_time": 30, "waiting_time": 0, "source_url": "", "internal": True,
        "keywords": [{"name": "Oven"}, {"name": "kip"}, {"name": "oven"}],
        "steps": [
            {"name": "", "instruction": "Snijd de kip in reepjes.", "time": 0, "ingredients": [
                food("kippendijen", 500.0, "gr"), food("knoflook", 2.0, "teentjes",
                                                       "Kruiden en specerijen")]},
            {"name": "", "instruction": "Breng op smaak.", "time": 0, "ingredients": [
                food("zout", 0.0, None, "Kruiden en specerijen"),
                food("peper", 0.0, None, None, no_amount=True),
                food("Voor de saus", 0.0, None, None, is_header=True),
                food("kaneel", 0.5, "theelepel", "Specerijen en sauzen", note="gemalen")]},
            {"name": "", "instruction": "", "time": 0, "ingredients": []},
        ],
    }


def picture(width=1200, height=800) -> bytes:
    out = io.BytesIO()
    Image.new("RGB", (width, height), (200, 120, 60)).save(out, "JPEG")
    return out.getvalue()


def export(*items: tuple[dict, bytes | None]) -> bytes:
    """Tandoor's export: a zip holding one zip per recipe."""
    outer = io.BytesIO()
    with zipfile.ZipFile(outer, "w") as zo:
        for n, (raw, image) in enumerate(items, start=1):
            inner = io.BytesIO()
            with zipfile.ZipFile(inner, "w") as zi:
                zi.writestr("recipe.json", json.dumps(raw))
                if image:
                    zi.writestr("image.jpg", image)
            zo.writestr(f"{n}.zip", inner.getvalue())
    return outer.getvalue()


@pytest.fixture
def db(store):
    recipes.ensure_tables(store)
    return store


def test_slug():
    assert tandoor.slug("Gesauteerde Kerstpaprika's") == "gesauteerde-kerstpaprikas"
    assert tandoor.slug("Crème brûlée (klassiek)") == "creme-brulee-klassiek"


def test_a_tandoor_recipe_becomes_one_cook_phase_to_review():
    body = tandoor.convert(tandoor_recipe())
    assert body["id"] == "kip-shoarma-uit-de-oven"
    assert body["tags"] == ["oven", "kip"]
    assert body["times"] == {"prep_min": 30, "cook_min": None}
    assert body["needs_review"] is True
    [phase] = body["phases"]
    assert (phase["name"], phase["kind"], len(phase["steps"])) == ("Bereiding", "cook", 2)
    assert phase["steps"][1]["ingredients"] == [
        {"name": "zout", "amount": None, "unit": "", "note": None, "pantry": True},
        {"name": "peper", "amount": None, "unit": "", "note": None, "pantry": False},
        {"name": "kaneel", "amount": 0.5, "unit": "tl", "note": "gemalen", "pantry": True}]
    first = phase["steps"][0]["ingredients"]
    assert [(i["unit"], i["pantry"]) for i in first] == [("g", False), ("teen", True)]


def test_the_import_saves_recipes_and_photos_once(db):
    data = export((tandoor_recipe(), picture()), (tandoor_recipe("Dal"), None),
                  (tandoor_recipe("Dal"), None))
    assert tandoor.run(db, data) == [
        "added    kip-shoarma-uit-de-oven, with photo needs review",
        "added    dal needs review",
        "added    dal-2 needs review"]
    assert photos.get(db, "kip-shoarma-uit-de-oven", "thumb") is not None
    assert tandoor.run(db, data)[0].startswith("skipped  kip-shoarma-uit-de-oven")


def test_phased_versions_replace_the_conversion_and_keep_the_photo(db):
    data = export((tandoor_recipe(), picture()))
    phased = {"recipes": [shoarma()]}
    assert tandoor.run(db, data, phased) == ["added    kip-shoarma-uit-de-oven, with photo"]
    saved = recipes.get(db, "kip-shoarma-uit-de-oven")
    assert saved["needs_review"] is False
    assert [p["kind"] for p in saved["recipe"]["phases"]] == ["prep", "prep", "cook"]


def test_faults_import_nothing(db):
    data = export((tandoor_recipe(), None))
    with pytest.raises(ValueError, match="not in the export"):
        tandoor.run(db, data, [shoarma() | {"id": "dal"}])
    with pytest.raises(ValueError, match="kip-shoarma-uit-de-oven: servings"):
        tandoor.run(db, data, [shoarma() | {"servings": "2"}])
    printed = tandoor.run(db, data, dry_run=True)
    assert json.loads(printed[0])[0]["id"] == "kip-shoarma-uit-de-oven"
    assert recipes.summaries(db) == []


def test_photos_are_shrunk_and_anything_else_is_refused():
    lead, thumb = photos.shrink(picture(2000, 1000))
    assert Image.open(io.BytesIO(lead)).size == (900, 450)
    assert Image.open(io.BytesIO(thumb)).size == (240, 240)
    small, _ = photos.shrink(picture(400, 300))
    assert Image.open(io.BytesIO(small)).size == (400, 300)
    with pytest.raises(ValueError):
        photos.shrink(b"<svg/>")


def test_the_photo_is_served_and_goes_with_its_recipe(db):
    tandoor.run(db, export((tandoor_recipe(), picture())))
    main.app.state.store = db
    main.app.state.config = {}
    client = TestClient(main.app)
    rid = "kip-shoarma-uit-de-oven"
    assert client.get("/api/recipes").json()["recipes"][0]["photo"]
    answer = client.get(f"/api/recipes/{rid}/photo/thumb")
    assert answer.headers["content-type"] == "image/webp"
    assert client.get(f"/api/recipes/{rid}/photo/huge").status_code == 422
    client.delete(f"/api/recipes/{rid}")
    assert photos.stamps(db) == {}
