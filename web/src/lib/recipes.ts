import { fold } from './fuzzy'
import type { Recipe, RecipeSummary } from './recipeTypes'

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

export const plural = (n: number, one: string, many = `${one}s`) => `${n} ${n === 1 ? one : many}`

/** "48 kB" for the Copy all note. */
export function kilobytes(text: string): string {
  return `${Math.max(1, Math.round(new Blob([text]).size / 1024))} kB`
}

const WEIGHED = ['g', 'kg', 'ml', 'l']
const FRACTIONS: [number, string][] = [[1 / 4, '¼'], [1 / 3, '⅓'], [1 / 2, '½'], [2 / 3, '⅔'], [3 / 4, '¾']]
const PLURAL: Record<string, string> = { teen: 'tenen' }

/** 2 decimals at most, with a Dutch comma: 1.5 → "1,5". */
const decimal = (n: number) => String(Math.round(n * 100) / 100).replace('.', ',')

/**
 * An amount as the recipe page shows it, times `factor` for other servings. Grams and
 * millilitres are rounded (to 5 from 50 up) and become kilos and litres from 1000; kilos and
 * litres get one decimal; anything else shows ½, ¼ or ⅓ where it is close, else a decimal
 * with a comma. Null is "naar smaak".
 */
export function amountText(amount: number | null, unit: string, factor = 1): string {
  if (amount == null) return 'naar smaak'
  // 1000 g and more reads as kilos, as on a shopping list.
  if ((unit === 'g' || unit === 'ml') && amount * factor >= 1000) return amountText(amount / 1000, unit === 'g' ? 'kg' : 'l', factor)
  const value = amount * factor
  let number: string
  if (unit === 'g' || unit === 'ml') number = String(value >= 50 ? Math.round(value / 5) * 5 : Math.max(1, Math.round(value)))
  else if (WEIGHED.includes(unit)) number = decimal(Math.round(value * 10) / 10)
  else {
    const whole = Math.floor(value + 1e-9)
    const rest = value - whole
    const fraction = FRACTIONS.find(([v]) => Math.abs(rest - v) < 0.04)
    if (rest < 0.04) number = String(whole)
    else if (rest > 0.96) number = String(whole + 1)
    else number = fraction ? `${whole || ''}${fraction[1]}` : decimal(value)
  }
  const many = value > 1 && PLURAL[unit]
  return [number, many || unit].filter(Boolean).join(' ')
}

export interface IngredientTotal {
  name: string
  pantry: boolean
  /** "150 g + 3 el", or "naar smaak" when no step gives an amount. */
  text: string
}

/** Each ingredient once by name (case ignored), amounts summed per unit, in recipe order. */
export function ingredientTotals(recipe: Recipe, factor = 1): IngredientTotal[] {
  const found = new Map<string, { name: string; pantry: boolean; byUnit: Map<string, number | null> }>()
  for (const phase of recipe.phases)
    for (const step of phase.steps)
      for (const ing of step.ingredients) {
        const key = ing.name.toLowerCase()
        const entry = found.get(key) ?? { name: ing.name, pantry: ing.pantry, byUnit: new Map() }
        found.set(key, entry)
        const had = entry.byUnit.get(ing.unit)
        if (ing.amount == null) {
          if (!entry.byUnit.has(ing.unit)) entry.byUnit.set(ing.unit, null)
        } else entry.byUnit.set(ing.unit, (had ?? 0) + ing.amount)
      }
  return [...found.values()].map(({ name, pantry, byUnit }) => {
    const parts = [...byUnit].filter(([, a]) => a != null || byUnit.size === 1)
    const known = parts.filter(([, a]) => a != null)
    const shown = known.length ? known : parts
    return { name, pantry, text: shown.map(([u, a]) => amountText(a, u, factor)).join(' + ') }
  })
}

/** Where the cook phases start, for the "All prepped" line; -1 when one kind is missing. */
export function firstCook(recipe: Recipe): number {
  const i = recipe.phases.findIndex((p) => p.kind === 'cook')
  return i > 0 ? i : -1
}
