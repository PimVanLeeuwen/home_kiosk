"""The recipe format `hub-recipe/1` (plan.md M30).

Recipes are written and changed with Claude and pasted in as JSON, so this schema is the real
editor: it is strict (unknown fields and text where a number belongs are refused) and every
fault is reported by its path in plain words. Phases are `prep` or `cook`, and every prep phase
comes before the first cook phase: the owner prepares everything before the heat goes on.
"""

from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    field_validator,
)
from pydantic_core import PydanticCustomError

SCHEMA_ID = "hub-recipe/1"
SLUG = r"^[a-z0-9]+(-[a-z0-9]+)*$"

# Put at the top of Copy all and the schema, so a Claude chat knows how these recipes work.
GUIDE = (
    "These are my recipes, in the format hub-recipe/1 (JSON). The recipes are in Dutch. "
    "I cook in phases: first every prep phase (cutting, marinating, mixing, setting apart), "
    "calmly, and only then the cook phases, where the oven or the pan goes on. So every phase "
    'is "prep" or "cook", and all prep phases come before the first cook phase. Each '
    "ingredient sits with the step that uses it; \"pantry\": true means I only check that I "
    "have it (spices, oil, salt), false means I have to get it. \"amount\": null means "
    '"naar smaak". "id" is a slug of the title; keep it the same when changing a recipe, so '
    "pasting it back replaces the old one. Answer with valid JSON in exactly this format."
)


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, str_strip_whitespace=True)


class Ingredient(_Strict):
    name: str = Field(min_length=1, max_length=80)
    amount: float | None = Field(gt=0, le=100_000)
    unit: str = Field(default="", max_length=20)
    note: str | None = Field(default=None, max_length=120)
    pantry: bool


class Step(_Strict):
    text: str = Field(min_length=1, max_length=2000)
    ingredients: list[Ingredient] = Field(default_factory=list, max_length=40)


class Phase(_Strict):
    name: str = Field(min_length=1, max_length=60)
    kind: Literal["prep", "cook"]
    steps: list[Step] = Field(min_length=1, max_length=30)


class Times(_Strict):
    prep_min: int | None = Field(default=None, ge=0, le=2880)
    cook_min: int | None = Field(default=None, ge=0, le=2880)


class Recipe(_Strict):
    schema_: Literal["hub-recipe/1"] = Field(alias="schema")
    id: str = Field(min_length=1, max_length=80, pattern=SLUG)
    title: str = Field(min_length=1, max_length=120)
    intro: str | None = Field(default=None, max_length=400)
    servings: int = Field(ge=1, le=50)
    tags: list[str] = Field(default_factory=list, max_length=12)
    source: str | None = Field(default=None, max_length=500)
    times: Times = Field(default_factory=Times)
    phases: list[Phase] = Field(min_length=1, max_length=20)
    notes: str | None = Field(default=None, max_length=4000)
    needs_review: bool = False

    model_config = ConfigDict(populate_by_name=True)

    @field_validator("tags")
    @classmethod
    def _tags(cls, tags: list[str]) -> list[str]:
        """Lower case, without a leading #, each once: "Oven" and "#oven" are the same tag."""
        out: list[str] = []
        for tag in tags:
            clean = tag.strip().lstrip("#").strip().lower()
            if not clean or len(clean) > 30:
                raise PydanticCustomError("tag", "a tag must be 1 to 30 characters")
            if clean not in out:
                out.append(clean)
        return out

    @field_validator("source")
    @classmethod
    def _source(cls, source: str | None) -> str | None:
        if source and not re.match(r"^https?://\S+$", source):
            raise PydanticCustomError("source", "the source must be a web address (http or https)")
        return source or None

    @field_validator("phases")
    @classmethod
    def _prep_first(cls, phases: list[Phase]) -> list[Phase]:
        first_cook = next((i for i, p in enumerate(phases) if p.kind == "cook"), None)
        if first_cook is None:
            return phases
        for i, phase in enumerate(phases[first_cook:], start=first_cook):
            if phase.kind == "prep":
                raise PydanticCustomError(
                    "phase_order",
                    '"{name}" is a prep phase after a cook phase. Move it before "{first}".',
                    {"index": i, "name": phase.name, "first": phases[first_cook].name},
                )
        return phases

    def dump(self) -> dict[str, Any]:
        """The canonical JSON: the field order above, `needs_review` only while it is true."""
        data = self.model_dump(mode="json", by_alias=True)
        if not data["needs_review"]:
            del data["needs_review"]
        return data


# Pydantic's error types in plain words; anything else keeps Pydantic's own message.
_PLAIN = {
    "missing": "is missing",
    "extra_forbidden": "is not a field of hub-recipe/1",
    "int_type": "should be a whole number",
    "float_type": "should be a number",
    "bool_type": "should be true or false",
    "string_type": "should be text",
    "list_type": "should be a list",
    "model_type": "should be an object",
    "dict_type": "should be an object",
    "literal_error": "should be {expected}",
    "string_too_short": "is empty",
    "string_too_long": "is too long (at most {max_length} characters)",
    "too_short": "needs at least {min_length}",
    "too_long": "has too many (at most {max_length})",
    "greater_than": "should be more than {gt}",
    "greater_than_equal": "should be {ge} or more",
    "less_than_equal": "should be {le} or less",
    "string_pattern_mismatch": "should be a slug: lower case letters, digits and hyphens",
}


def path_of(loc: tuple[Any, ...]) -> str:
    """("phases", 3, "steps", 0) becomes "phases[3].steps[0]"."""
    out = ""
    for part in loc:
        if isinstance(part, int):
            out += f"[{part}]"
        else:
            name = "schema" if part == "schema_" else str(part)
            out += f".{name}" if out else name
    return out


def problems(error: ValidationError, prefix: str = "") -> list[dict[str, str]]:
    """Every fault as {path, message}, in plain words, for the paste screen."""
    out = []
    for err in error.errors():
        loc = tuple(err["loc"])
        ctx = err.get("ctx") or {}
        kind = err["type"]
        if kind == "phase_order":
            loc = (*loc, ctx["index"])
            message = err["msg"]
        elif kind in ("int_type", "float_type") and isinstance(err.get("input"), str):
            message = f"is text; it should be a number, like {_example(loc)}"
        elif kind in _PLAIN:
            message = _PLAIN[kind].format(**ctx)
        else:
            message = err["msg"]
        if kind == "missing" and loc and loc[-1] == "pantry":
            loc = loc[:-1]
            message = "has no pantry: say true (just check) or false (to get)"
        path = path_of(loc)
        if prefix:
            path = f"{prefix}.{path}" if path else prefix
        out.append({"path": path or "(the recipe)", "message": message})
    return out


def _example(loc: tuple[Any, ...]) -> str:
    return {"servings": "2", "prep_min": "20", "cook_min": "30"}.get(str(loc[-1]), "250")


def parse(data: Any) -> Recipe:
    """A recipe from pasted JSON, or a ValidationError (use `problems`)."""
    return Recipe.model_validate(data)


def json_schema() -> dict[str, Any]:
    return Recipe.model_json_schema(by_alias=True)
