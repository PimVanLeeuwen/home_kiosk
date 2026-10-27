import type { Recipe, RecipeDetail, RecipeList, RecipeSummary } from '../lib/recipeTypes'

/** Made-up recipes for page tests. */
export function recipe(over: Partial<RecipeSummary> = {}): RecipeSummary {
  return {
    id: 'kip-shoarma-uit-de-oven',
    title: 'Kip shoarma uit de oven',
    tags: ['oven', 'kip'],
    times: { prep_min: 30, cook_min: 30 },
    servings: 2,
    needs_review: false,
    updated_at: '2026-10-27T18:00:00+00:00',
    photo: '2026-10-27T18:00:00+00:00',
    ...over,
  }
}

export const RECIPES: RecipeList = {
  as_of: '2026-10-27T18:00:00+00:00',
  stale: false,
  count: 3,
  review_count: 1,
  tags: [
    { tag: 'oven', count: 2 },
    { tag: 'kip', count: 1 },
    { tag: 'vega', count: 1 },
  ],
  recipes: [
    recipe({ id: 'crème-brulee', title: 'Crème brûlée', tags: ['oven'], times: { prep_min: 20, cook_min: 260 } }),
    recipe(),
    recipe({ id: 'dal', title: 'Dal met spinazie', tags: ['vega'], times: { prep_min: 15, cook_min: null }, needs_review: true, photo: null }),
  ],
}

/** A whole made-up recipe: two prep phases, two cook phases. */
export const SHOARMA: Recipe = {
  "schema": "hub-recipe/1" as const,
  "id": "kip-shoarma",
  "title": "Kip shoarma uit de oven",
  "intro": "Gemarineerde kippendijen met geroosterde ui en paprika, pita en een koude knoflooksaus.",
  "servings": 2,
  "tags": [
    "oven",
    "doordeweeks",
    "kip"
  ],
  "source": "https://example.com/recepten/kip-shoarma",
  "times": {
    "prep_min": 30,
    "cook_min": 30
  },
  "phases": [
    {
      "name": "Marinade",
      "kind": "prep" as const,
      "steps": [
        {
          "text": "Snijd de kippendijen in reepjes van een vinger dik.",
          "ingredients": [
            {
              "name": "kippendijen",
              "amount": 500,
              "unit": "g",
              "note": null,
              "pantry": false
            }
          ]
        },
        {
          "text": "Meng yoghurt, olijfolie, knoflook en de specerijen. Schep de kip erdoor en laat minstens 20 minuten staan.",
          "ingredients": [
            {
              "name": "Griekse yoghurt",
              "amount": 3,
              "unit": "el",
              "note": null,
              "pantry": false
            },
            {
              "name": "olijfolie",
              "amount": 2,
              "unit": "el",
              "note": null,
              "pantry": true
            },
            {
              "name": "knoflook",
              "amount": 2,
              "unit": "teen",
              "note": "geraspt",
              "pantry": true
            },
            {
              "name": "komijn",
              "amount": 1,
              "unit": "tl",
              "note": null,
              "pantry": true
            },
            {
              "name": "gerookt paprikapoeder",
              "amount": 2,
              "unit": "tl",
              "note": null,
              "pantry": true
            },
            {
              "name": "kaneel",
              "amount": 0.25,
              "unit": "tl",
              "note": null,
              "pantry": true
            },
            {
              "name": "zout",
              "amount": 1,
              "unit": "tl",
              "note": null,
              "pantry": true
            }
          ]
        }
      ]
    },
    {
      "name": "Knoflooksaus",
      "kind": "prep" as const,
      "steps": [
        {
          "text": "Roer yoghurt, knoflook, citroensap en een snuf zout door elkaar. Zet koud.",
          "ingredients": [
            {
              "name": "Griekse yoghurt",
              "amount": 150,
              "unit": "g",
              "note": null,
              "pantry": false
            },
            {
              "name": "knoflook",
              "amount": 1,
              "unit": "teen",
              "note": null,
              "pantry": true
            },
            {
              "name": "citroen",
              "amount": 0.5,
              "unit": "",
              "note": "het sap",
              "pantry": false
            },
            {
              "name": "zout",
              "amount": null,
              "unit": "",
              "note": null,
              "pantry": true
            }
          ]
        }
      ]
    },
    {
      "name": "Oven",
      "kind": "cook" as const,
      "steps": [
        {
          "text": "Verwarm de oven voor op 220 °C.",
          "ingredients": []
        },
        {
          "text": "Verdeel kip, ui en paprika over een bakplaat met bakpapier. 25 minuten in de oven, halverwege omscheppen.",
          "ingredients": []
        }
      ]
    },
    {
      "name": "Afmaken",
      "kind": "cook" as const,
      "steps": [
        {
          "text": "Warm de pita's de laatste 3 minuten mee.",
          "ingredients": [
            {
              "name": "pitabroodjes",
              "amount": 4,
              "unit": "",
              "note": null,
              "pantry": false
            }
          ]
        },
        {
          "text": "Vul de pita's met kip, groente en peterselie; saus erover.",
          "ingredients": []
        }
      ]
    }
  ],
  "notes": null
}

export function detail(over: Partial<RecipeDetail> = {}): RecipeDetail {
  return {
    recipe: SHOARMA,
    needs_review: false,
    created_at: '2026-10-20T18:00:00+00:00',
    updated_at: '2026-10-27T18:00:00+00:00',
    previous_at: null,
    photo: '2026-10-27T18:00:00+00:00',
    ...over,
  }
}
