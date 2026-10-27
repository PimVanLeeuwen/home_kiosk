import type { RecipeList, RecipeSummary } from '../lib/recipeTypes'

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
