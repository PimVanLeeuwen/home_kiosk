"""What a pasted recipe changes, in a few lines, shown before it replaces the old one."""

from __future__ import annotations

from typing import Any

FRACTIONS = {0.25: "¼", 1 / 3: "⅓", 0.5: "½", 2 / 3: "⅔", 0.75: "¾"}
WEIGHED = ("g", "kg", "ml", "l")


def amount_text(amount: float | None, unit: str = "") -> str:
    """2.5 el becomes "2½ el", 0.25 tl "¼ tl", 1.5 kg "1,5 kg", None "naar smaak"."""
    if amount is None:
        return "naar smaak"
    whole = int(amount)
    rest = amount - whole
    if rest < 1e-6:
        number = str(whole)
    elif unit not in WEIGHED and (frac := _fraction(rest)):
        number = f"{whole or ''}{frac}"
    else:
        number = f"{amount:.2f}".rstrip("0").rstrip(".").replace(".", ",")
    return f"{number} {unit}".strip()


def _fraction(rest: float) -> str | None:
    return next((s for v, s in FRACTIONS.items() if abs(rest - v) < 0.02), None)


def totals(recipe: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Each ingredient once by name, its amounts summed per unit ("150 g + 3 el")."""
    found: dict[str, dict[str, Any]] = {}
    for phase in recipe["phases"]:
        for step in phase["steps"]:
            for ing in step["ingredients"]:
                entry = found.setdefault(ing["name"].lower(), {
                    "name": ing["name"], "pantry": ing["pantry"], "by_unit": {}})
                units = entry["by_unit"]
                if ing["amount"] is None:
                    units.setdefault(ing["unit"], None)
                elif units.get(ing["unit"]) is None:
                    units[ing["unit"]] = ing["amount"]
                else:
                    units[ing["unit"]] += ing["amount"]
    for entry in found.values():
        parts = [(u, a) for u, a in entry["by_unit"].items()
                 if a is not None or len(entry["by_unit"]) == 1]
        entry["text"] = " + ".join(amount_text(a, u) for u, a in parts)
    return found


def changes(old: dict[str, Any], new: dict[str, Any]) -> list[dict[str, str]]:
    """Lines like {"kind": "changed", "text": "kaneel: ¼ tl instead of ½ tl"}."""
    out: list[dict[str, str]] = []

    def add(kind: str, text: str) -> None:
        out.append({"kind": kind, "text": text})

    if old["title"] != new["title"]:
        add("changed", f'Title: "{new["title"]}" instead of "{old["title"]}"')
    if old["servings"] != new["servings"]:
        add("changed", f'Servings: {new["servings"]} instead of {old["servings"]}')
    for label, key in (("Prep time", "prep_min"), ("Cook time", "cook_min")):
        was, now = old["times"].get(key), new["times"].get(key)
        if was != now:
            add("changed", f"{label}: {_minutes(now)} instead of {_minutes(was)}")
    for tag in new["tags"]:
        if tag not in old["tags"]:
            add("added", f'Tag "{tag}"')
    for tag in old["tags"]:
        if tag not in new["tags"]:
            add("removed", f'Tag "{tag}"')
    for key, label in (("intro", "Intro"), ("notes", "Notes"), ("source", "Source")):
        if old.get(key) != new.get(key):
            add("changed", f"{label} changed")
    if old.get("needs_review") and not new.get("needs_review"):
        add("changed", "No longer needs review")

    _phases(old["phases"], new["phases"], add)

    was, now = totals(old), totals(new)
    for key, ing in now.items():
        before = was.get(key)
        if before is None:
            add("added", f'Ingredient "{ing["name"]}" ({ing["text"]})')
        elif before["text"] != ing["text"]:
            add("changed", f'{ing["name"]}: {ing["text"]} instead of {before["text"]}')
        elif before["pantry"] != ing["pantry"]:
            where = "pantry, just check" if ing["pantry"] else "to get"
            add("changed", f'{ing["name"]}: now {where}')
    for key, ing in was.items():
        if key not in now:
            add("removed", f'Ingredient "{ing["name"]}"')
    return out


def _minutes(value: int | None) -> str:
    return "none" if value is None else f"{value} min"


def _steps(n: int) -> str:
    return f"{n} step" if n == 1 else f"{n} steps"


def _phases(old: list[dict[str, Any]], new: list[dict[str, Any]], add: Any) -> None:
    before = {p["name"]: p for p in old}
    after = {p["name"]: p for p in new}
    for phase in new:
        was = before.get(phase["name"])
        if was is None:
            add("added", f'New {phase["kind"]} phase "{phase["name"]}", '
                         f'{_steps(len(phase["steps"]))}')
            continue
        if was["kind"] != phase["kind"]:
            add("changed", f'"{phase["name"]}" is now a {phase["kind"]} phase')
        a, b = was["steps"], phase["steps"]
        for i in range(max(len(a), len(b))):
            if i >= len(a):
                add("added", f'{phase["name"]}: new step {i + 1}')
            elif i >= len(b):
                add("removed", f'{phase["name"]}: step {i + 1}')
            elif a[i]["text"] != b[i]["text"]:
                add("changed", f'{phase["name"]}: step {i + 1} reworded')
    for phase in old:
        if phase["name"] not in after:
            add("removed", f'Phase "{phase["name"]}"')
    kept_old = [p["name"] for p in old if p["name"] in after]
    kept_new = [p["name"] for p in new if p["name"] in before]
    if kept_old != kept_new:
        add("changed", "The phases are in a new order")
