"""The recipe format, its plain-word faults, the change summary and the store (plan.md M30)."""

from __future__ import annotations

import copy

import pytest
from pydantic import ValidationError

from app.recipes import schema
from app.recipes import store as recipes
from app.recipes.changes import amount_text, changes


def ing(name, amount, unit="", pantry=False, **more):
    return {"name": name, "amount": amount, "unit": unit, "pantry": pantry, **more}


def shoarma() -> dict:
    return {
        "schema": "hub-recipe/1", "id": "kip-shoarma-uit-de-oven",
        "title": "Kip shoarma uit de oven", "servings": 2, "tags": ["oven", "doordeweeks"],
        "times": {"prep_min": 30, "cook_min": 30},
        "phases": [
            {"name": "Marinade", "kind": "prep", "steps": [
                {"text": "Snijd de kip in reepjes.", "ingredients": [ing("kippendijen", 500, "g")]},
                {"text": "Meng yoghurt en specerijen; schep de kip erdoor.", "ingredients": [
                    ing("Griekse yoghurt", 3, "el"), ing("kaneel", 0.5, "tl", True),
                    ing("zout", None, pantry=True)]}]},
            {"name": "Knoflooksaus", "kind": "prep", "steps": [
                {"text": "Roer yoghurt en knoflook door elkaar.", "ingredients": [
                    ing("Griekse yoghurt", 150, "g"), ing("zout", 1, "tl", True)]}]},
            {"name": "Oven", "kind": "cook", "steps": [
                {"text": "Oven op 220 °C, 25 minuten."}]},
        ],
    }


@pytest.fixture
def db(store):
    recipes.ensure_tables(store)
    return store


def faults(data) -> list[dict[str, str]]:
    with pytest.raises(ValidationError) as exc:
        schema.parse(data)
    return schema.problems(exc.value)


def test_a_valid_recipe_is_kept_in_its_canonical_form():
    data = shoarma()
    data["tags"] = ["Oven", "#oven", "doordeweeks"]
    body = schema.parse(data).dump()
    assert body["tags"] == ["oven", "doordeweeks"]
    assert list(body)[:3] == ["schema", "id", "title"]
    assert "needs_review" not in body
    assert body["phases"][2]["steps"][0]["ingredients"] == []


def test_faults_are_given_by_path_in_plain_words():
    data = shoarma()
    data["servings"] = "2"
    data["colour"] = "red"
    del data["phases"][0]["steps"][0]["ingredients"][0]["pantry"]
    assert faults(data) == [
        {"path": "servings", "message": "is text; it should be a number, like 2"},
        {"path": "phases[0].steps[0].ingredients[0]",
         "message": "has no pantry: say true (just check) or false (to get)"},
        {"path": "colour", "message": "is not a field of hub-recipe/1"},
    ]


def test_a_prep_phase_after_the_heat_is_refused():
    data = shoarma()
    data["phases"].append({"name": "Salade", "kind": "prep", "steps": [{"text": "Snijd."}]})
    assert faults(data) == [{"path": "phases[3]", "message":
                             '"Salade" is a prep phase after a cook phase. Move it before "Oven".'}]


@pytest.mark.parametrize("field,value,message", [
    ("id", "Kip Shoarma", "should be a slug: lower case letters, digits and hyphens"),
    ("schema", "hub-recipe/2", "should be 'hub-recipe/1'"),
    ("source", "javascript:alert(1)", "the source must be a web address (http or https)"),
    ("phases", [], "needs at least 1"),
])
def test_other_faults(field, value, message):
    data = shoarma()
    data[field] = value
    assert [f["message"] for f in faults(data)] == [message]


@pytest.mark.parametrize("amount,unit,text", [
    (None, "", "naar smaak"), (2, "", "2"), (0.25, "tl", "¼ tl"), (2.5, "el", "2½ el"),
    (1.5, "kg", "1,5 kg"), (0.5, "", "½"), (1 / 3, "kop", "⅓ kop"), (1.2, "el", "1,2 el"),
])
def test_amount_text(amount, unit, text):
    assert amount_text(amount, unit) == text


def test_changes_summarise_a_new_version():
    old = schema.parse(shoarma()).dump()
    data = shoarma()
    data["needs_review"] = False
    data["phases"][0]["steps"][1]["ingredients"][1]["amount"] = 0.25
    data["phases"][0]["steps"][1]["ingredients"].append(ing("komijn", 1, "tl", True))
    del data["phases"][1]
    data["phases"][1]["steps"].append({"text": "Pita's de laatste 3 minuten mee."})
    data["tags"] = ["oven"]
    new = schema.parse(data).dump()
    assert changes(old, new) == [
        {"kind": "removed", "text": 'Tag "doordeweeks"'},
        {"kind": "added", "text": "Oven: new step 2"},
        {"kind": "removed", "text": 'Phase "Knoflooksaus"'},
        {"kind": "changed", "text": "Griekse yoghurt: 3 el instead of 3 el + 150 g"},
        {"kind": "changed", "text": "kaneel: ¼ tl instead of ½ tl"},
        {"kind": "changed", "text": "zout: naar smaak instead of 1 tl"},
        {"kind": "added", "text": 'Ingredient "komijn" (1 tl)'},
    ]


def test_store_adds_replaces_and_undoes_once(db):
    first = schema.parse(shoarma())
    assert recipes.save(db, first) == "added"
    assert recipes.save(db, first) == "unchanged"
    data = shoarma()
    data["title"] = "Kip shoarma"
    assert recipes.save(db, schema.parse(data)) == "replaced"
    assert recipes.summaries(db)[0]["title"] == "Kip shoarma"
    assert recipes.get(db, first.id)["previous_at"] is not None

    assert recipes.undo(db, first.id)
    assert recipes.get(db, first.id)["recipe"]["title"] == "Kip shoarma uit de oven"
    assert not recipes.undo(db, first.id)

    assert recipes.delete(db, first.id)
    assert recipes.get(db, first.id) is None


def test_summaries_are_by_title_and_carry_no_phases(db):
    for title, rid in (("risotto", "risotto"), ("Aubergine", "aubergine")):
        data = copy.deepcopy(shoarma()) | {"title": title, "id": rid, "needs_review": True}
        recipes.save(db, schema.parse(data))
    rows = recipes.summaries(db)
    assert [r["title"] for r in rows] == ["Aubergine", "risotto"]
    assert rows[0]["needs_review"] is True
    assert "phases" not in rows[0]
