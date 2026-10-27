import type { Recipe } from './recipeTypes'

/** One screen of cook mode: a phase, or the "All prepped" pause before the first cook phase. */
export type CookView = { kind: 'phase'; phase: number } | { kind: 'pause' }

/** Where cook mode is and what is ticked, kept on the phone for the day (plan.md M30). */
export interface CookState {
  /** The local day it belongs to; another day starts over. */
  day: string
  /** The recipe's `updated_at`; a pasted version starts over too. */
  version: string
  view: number
  /** Ticked steps as "phase.step". */
  ticks: string[]
}

export const COOK_KEY = 'hub.cook'

export const stepKey = (phase: number, step: number) => `${phase}.${step}`

/** "2026-10-27" in the phone's own time zone. */
export function localDay(now = new Date()): string {
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`
}

/** Every phase in order, with the pause only between the last prep phase and the first cook phase. */
export function cookViews(recipe: Recipe): CookView[] {
  const firstCook = recipe.phases.findIndex((p) => p.kind === 'cook')
  return recipe.phases.flatMap((_, phase): CookView[] =>
    phase === firstCook && firstCook > 0 ? [{ kind: 'pause' }, { kind: 'phase', phase }] : [{ kind: 'phase', phase }],
  )
}

type Saved = Record<string, CookState>

function readAll(): Saved {
  try {
    const value: unknown = JSON.parse(localStorage.getItem(COOK_KEY) ?? '{}')
    return value && typeof value === 'object' && !Array.isArray(value) ? (value as Saved) : {}
  } catch {
    return {}
  }
}

/** Today's progress for this version of the recipe, or a fresh start. */
export function loadCook(id: string, version: string, viewCount: number, now = new Date()): CookState {
  const saved = readAll()[id]
  const day = localDay(now)
  if (!saved || saved.day !== day || saved.version !== version || !Array.isArray(saved.ticks)) {
    return { day, version, view: 0, ticks: [] }
  }
  const view = Number.isInteger(saved.view) ? Math.min(Math.max(saved.view, 0), viewCount - 1) : 0
  return { day, version, view, ticks: saved.ticks.filter((t) => typeof t === 'string') }
}

/** Keeps this recipe's progress and drops other days' (no storage, no keeping). */
export function saveCook(id: string, state: CookState): void {
  try {
    const kept = Object.fromEntries(Object.entries(readAll()).filter(([key, s]) => key !== id && s?.day === state.day))
    localStorage.setItem(COOK_KEY, JSON.stringify({ ...kept, [id]: state }))
  } catch {
    // Private browsing without storage: ticks last until the page closes.
  }
}

export function toggleTick(state: CookState, key: string): CookState {
  const ticks = state.ticks.includes(key) ? state.ticks.filter((t) => t !== key) : [...state.ticks, key]
  return { ...state, ticks }
}

/** How many of a phase's steps are ticked. */
export function phaseDone(recipe: Recipe, ticks: string[], phase: number): number {
  return recipe.phases[phase].steps.filter((_, s) => ticks.includes(stepKey(phase, s))).length
}
