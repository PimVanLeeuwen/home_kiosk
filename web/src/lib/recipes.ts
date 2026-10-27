import { fold } from './fuzzy'
import type { RecipeSummary } from './recipeTypes'

/** The list's chips: everything, one tag, or the recipes still to review. */
export type RecipeFilter = { kind: 'all' } | { kind: 'tag'; tag: string } | { kind: 'review' }

/** Recipes whose title has every word typed (accents ignored) and that pass the chip. */
export function filterRecipes(recipes: RecipeSummary[], query: string, filter: RecipeFilter): RecipeSummary[] {
  const words = fold(query).split(/\s+/).filter(Boolean)
  return recipes.filter((r) => {
    if (filter.kind === 'tag' && !r.tags.includes(filter.tag)) return false
    if (filter.kind === 'review' && !r.needs_review) return false
    const title = fold(r.title)
    return words.every((w) => title.includes(w))
  })
}

/** 25 → "25 min", 260 → "4 h 20 min", 120 → "2 h". */
export function duration(minutes: number): string {
  if (minutes < 60) return `${minutes} min`
  const h = Math.floor(minutes / 60)
  const m = minutes % 60
  return m ? `${h} h ${m} min` : `${h} h`
}

/** The photo's address; its stamp makes a new photo a new address, so each may be kept. */
export function photoUrl(recipe: Pick<RecipeSummary, 'id' | 'photo'>, size: 'lead' | 'thumb'): string {
  return `/api/recipes/${encodeURIComponent(recipe.id)}/photo/${size}?v=${encodeURIComponent(recipe.photo ?? '')}`
}

/** "48 kB" for the Copy all note. */
export function kilobytes(text: string): string {
  return `${Math.max(1, Math.round(new Blob([text]).size / 1024))} kB`
}
