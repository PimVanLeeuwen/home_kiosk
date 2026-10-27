/** The hub's recipes (plan.md M30): /api/recipes and the paste endpoints. */

export interface RecipeTimes {
  prep_min: number | null
  cook_min: number | null
}

export interface RecipeSummary {
  id: string
  title: string
  tags: string[]
  times: RecipeTimes
  servings: number | null
  needs_review: boolean
  updated_at: string
  /** When the photo was stored, or null without one; part of the photo's address. */
  photo: string | null
}

export interface RecipeList {
  as_of: string
  stale: boolean
  count: number
  review_count: number
  tags: { tag: string; count: number }[]
  recipes: RecipeSummary[]
}

export interface PasteProblem {
  path: string
  message: string
}

export interface PasteChange {
  kind: 'added' | 'changed' | 'removed'
  text: string
}

/** What a paste would do, from POST /api/recipes/check. */
export interface PasteCheck {
  ok: boolean
  problems: PasteProblem[]
  recipes: { id: string; title: string; result: 'new' | 'replace' | 'same'; changes: PasteChange[] }[]
}

export interface PasteSaved {
  saved: { id: string; title: string; result: 'added' | 'replaced' | 'unchanged' }[]
}

export interface RecipeExport {
  schema: string
  guide: string
  json_schema: unknown
  recipes: unknown[]
}
