"""The one-time import of Tandoor's export (plan.md M30, step 2), run by hand on the NAS:

    docker cp export.zip home-kiosk-collector:/tmp/
    docker exec home-kiosk-collector python -m app.recipes.tandoor /tmp/export.zip

Tandoor's default export is a zip of zips, one per recipe, each with `recipe.json` and an
`image.*`. Its steps have no names, so every recipe comes in as one cook phase "Bereiding",
marked needs review; foods in Tandoor's spice and oil categories are guessed as pantry.
`--phased file.json` uses reworked versions (one recipe, a list or Copy all's JSON, matched
by id) instead, with Tandoor's photos. `--dry-run` prints the recipes and saves nothing.
"""

from __future__ import annotations

import argparse
import io
import json
import re
import sys
import unicodedata
import zipfile
from pathlib import PurePosixPath
from typing import Any

from pydantic import ValidationError

from .. import config
from ..store import Store
from . import photos, schema
from . import store as recipes

PANTRY_CATEGORIES = {"kruiden en specerijen", "olie en azijn", "specerijen en sauzen"}
UNITS = {
    "theelepel": "tl", "theelepels": "tl", "eetlepel": "el", "eetlepels": "el",
    "teen": "teen", "tenen": "teen", "teentje": "teen", "teentjes": "teen",
    "gr": "g", "gram": "g", "kilo": "kg", "kilogram": "kg", "milliliter": "ml",
    "liter": "l", "stuk": "", "stuks": "",
}
MAX_INNER = 30 * 1024 * 1024  # one recipe's zip, its photo included
MAX_RECIPES = 2000


def slug(title: str) -> str:
    """ "Gesauteerde Kerstpaprika's" becomes "gesauteerde-kerstpaprikas"."""
    plain = unicodedata.normalize("NFKD", title).encode("ascii", "ignore").decode().lower()
    plain = plain.replace("'", "")
    return re.sub(r"[^a-z0-9]+", "-", plain).strip("-")[:80].strip("-") or "recept"


def _unit(raw: dict[str, Any] | None) -> str:
    name = ((raw or {}).get("name") or "").strip().lower()
    return UNITS.get(name, name)[:20]


def _ingredient(raw: dict[str, Any]) -> dict[str, Any] | None:
    food = raw.get("food") or {}
    if raw.get("is_header") or not food.get("name"):
        return None
    amount = raw.get("amount") or 0
    category = ((food.get("supermarket_category") or {}).get("name") or "").lower()
    return {"name": food["name"].strip()[:80],
            "amount": None if raw.get("no_amount") or amount <= 0 else float(amount),
            "unit": _unit(raw.get("unit")), "note": (raw.get("note") or "").strip()[:120] or None,
            "pantry": category in PANTRY_CATEGORIES}


def convert(raw: dict[str, Any], rid: str | None = None) -> dict[str, Any]:
    """Tandoor's recipe.json as hub-recipe/1, valid but in one cook phase, needing review."""
    steps = []
    for step in raw.get("steps") or []:
        text = (step.get("instruction") or "").strip()
        ingredients = [i for i in map(_ingredient, step.get("ingredients") or []) if i]
        if text or ingredients:
            steps.append({"text": text or "(geen tekst)", "ingredients": ingredients})
    description = (raw.get("description") or "").strip()
    source = (raw.get("source_url") or "").strip()
    tags = [k["name"] for k in raw.get("keywords") or [] if (k.get("name") or "").strip()]
    return {
        "schema": schema.SCHEMA_ID,
        "id": rid or slug(raw["name"]),
        "title": raw["name"].strip()[:120],
        "intro": description if 0 < len(description) <= 400 else None,
        "servings": max(1, min(50, int(raw.get("servings") or 1))),
        "tags": list(dict.fromkeys(t.strip().lower()[:30] for t in tags))[:12],
        "source": source if re.match(r"^https?://\S+$", source) else None,
        "times": {"prep_min": raw.get("working_time") or None,
                  "cook_min": raw.get("waiting_time") or None},
        "phases": [{"name": "Bereiding", "kind": "cook",
                    "steps": steps or [{"text": "(geen stappen)", "ingredients": []}]}],
        "notes": description if len(description) > 400 else None,
        "needs_review": True,
    }


def read_export(data: bytes) -> list[tuple[dict[str, Any], bytes | None]]:
    """(converted recipe, photo bytes or None) for every recipe in the export, read in memory."""
    out: list[tuple[dict[str, Any], bytes | None]] = []
    taken: set[str] = set()
    with zipfile.ZipFile(io.BytesIO(data)) as outer:
        inner_names = sorted((n for n in outer.namelist() if n.endswith(".zip")),
                             key=lambda n: (len(n), n))[:MAX_RECIPES]
        for name in inner_names:
            if outer.getinfo(name).file_size > MAX_INNER:
                raise ValueError(f"{name} is too large")
            with zipfile.ZipFile(io.BytesIO(outer.read(name))) as inner:
                files = {PurePosixPath(n).name: n for n in inner.namelist()}
                raw = json.loads(inner.read(files["recipe.json"]))
                image = next((files[n] for n in files if n.startswith("image.")), None)
                picture = inner.read(image) if image and (
                    inner.getinfo(image).file_size <= photos.MAX_BYTES) else None
            rid, n = slug(raw["name"]), 2
            while rid in taken:
                rid, n = f"{slug(raw['name'])[:76]}-{n}", n + 1
            taken.add(rid)
            out.append((convert(raw, rid), picture))
    return out


def run(store: Store, export: bytes, phased: Any = None, replace: bool = False,
        dry_run: bool = False) -> list[str]:
    """Imports the export and returns one line per recipe; raises ValueError on faults."""
    found = read_export(export)
    better: dict[str, dict[str, Any]] = {}
    if phased is not None:
        items = phased["recipes"] if isinstance(phased, dict) and "recipes" in phased else (
            phased if isinstance(phased, list) else [phased])
        better = {item.get("id"): item for item in items if isinstance(item, dict)}
        unknown = sorted(set(better) - {body["id"] for body, _ in found}, key=str)
        if unknown:
            raise ValueError(f"--phased has ids that are not in the export: {unknown}")
    parsed = []
    faults = []
    for body, picture in found:
        try:
            parsed.append((schema.parse(better.get(body["id"], body)), picture))
        except ValidationError as exc:
            faults += [f'{body["id"]}: {p["path"]} {p["message"]}'
                       for p in schema.problems(exc)]
    if faults:
        raise ValueError("\n".join(faults))
    if dry_run:
        return [json.dumps([r.dump() for r, _ in parsed], ensure_ascii=False, indent=2)]
    lines = []
    existing = recipes.bodies(store, [r.id for r, _ in parsed])
    for recipe, picture in parsed:
        if recipe.id in existing and not replace:
            lines.append(f"skipped  {recipe.id} (already in the hub; --replace to overwrite)")
            continue
        result = recipes.save(store, recipe)
        note = ""
        if picture:
            try:
                photos.put(store, recipe.id, picture)
                note = ", with photo"
            except ValueError as exc:
                note = f", photo left out ({exc})"
        review = " needs review" if recipe.needs_review else ""
        lines.append(f"{result:8} {recipe.id}{note}{review}")
    return lines


def main(argv: list[str] | None = None) -> int:
    ask = argparse.ArgumentParser(prog="python -m app.recipes.tandoor",
                                  description="Import Tandoor's export into the hub's recipes.")
    ask.add_argument("export", help="the zip Tandoor's export made")
    ask.add_argument("--phased", help="reworked recipes as JSON, used instead (by id)")
    ask.add_argument("--replace", action="store_true", help="overwrite recipes already there")
    ask.add_argument("--dry-run", action="store_true", help="print the recipes, save nothing")
    args = ask.parse_args(argv)

    with open(args.export, "rb") as fh:
        export = fh.read()
    phased = None
    if args.phased:
        with open(args.phased, encoding="utf-8") as fh:
            phased = json.load(fh)
    cfg = config.load()
    store = Store(cfg.get("database", "./data/collector.db"))
    recipes.ensure_tables(store)
    try:
        lines = run(store, export, phased, args.replace, args.dry_run)
    except (ValueError, KeyError, zipfile.BadZipFile) as exc:
        print(f"Nothing imported: {exc}", file=sys.stderr)
        return 1
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
