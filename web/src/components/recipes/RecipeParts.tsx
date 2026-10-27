import { Flame, Minus, Plus } from 'lucide-react'
import { Fragment } from 'react'
import { cn } from '../../lib/cn'
import { amountText, duration, firstCook, ingredientTotals } from '../../lib/recipes'
import type { Ingredient, Phase, Recipe } from '../../lib/recipeTypes'
import { Surface } from '../ui/Card'

const tile = 'flex min-w-0 flex-1 flex-col rounded-[12px] border border-line-soft bg-card px-3 py-2'

/** Prep and cook time in their colours, and the persons the amounts are for. */
export function Facts({ recipe, servings, onServings }: { recipe: Recipe; servings: number; onServings: (n: number) => void }) {
  const { prep_min: prep, cook_min: cook } = recipe.times
  return (
    <div className="flex gap-2">
      {!!prep && (
        <div className={tile}>
          <span className="text-label text-faint">Prep</span>
          <span className="text-title font-semibold text-accent-fg">{duration(prep)}</span>
        </div>
      )}
      {!!cook && (
        <div className={tile}>
          <span className="text-label text-faint">Cook</span>
          <span className="text-title font-semibold text-cook">{duration(cook)}</span>
        </div>
      )}
      <div className={cn(tile, 'flex-[1.2]')}>
        <span className="text-label text-faint">Persons</span>
        <span className="flex items-center gap-2.5">
          <button type="button" aria-label="Fewer persons" disabled={servings <= 1} onClick={() => onServings(servings - 1)} className="grid size-7 place-items-center rounded-lg border border-line bg-raised disabled:opacity-40">
            <Minus aria-hidden="true" className="size-3.5" />
          </button>
          <output aria-label="Persons" className="min-w-5 text-center text-title font-semibold">
            {servings}
          </output>
          <button type="button" aria-label="More persons" disabled={servings >= 50} onClick={() => onServings(servings + 1)} className="grid size-7 place-items-center rounded-lg border border-line bg-raised disabled:opacity-40">
            <Plus aria-hidden="true" className="size-3.5" />
          </button>
        </span>
      </div>
    </div>
  )
}

/** What to get as a list with amounts; what to only check (the pantry) as small chips. */
export function IngredientLists({ recipe, factor }: { recipe: Recipe; factor: number }) {
  const all = ingredientTotals(recipe, factor)
  const get = all.filter((i) => !i.pantry)
  const check = all.filter((i) => i.pantry)
  return (
    <div className="flex flex-col gap-4">
      {get.length > 0 && (
        <section aria-label="To get" className="flex flex-col gap-2">
          <h2 className="flex justify-between text-small font-semibold text-muted">
            To get <span className="font-normal text-faint">{get.length} {get.length === 1 ? 'item' : 'items'}</span>
          </h2>
          <ul className="overflow-hidden rounded-[14px] border border-line-soft bg-card">
            {get.map((i) => (
              <li key={i.name} className="flex justify-between gap-3 border-t border-line-soft px-3.5 py-2 first:border-t-0">
                <span>{i.name}</span>
                <span className="text-right font-semibold whitespace-nowrap">{i.text}</span>
              </li>
            ))}
          </ul>
        </section>
      )}
      {check.length > 0 && (
        <section aria-label="Check" className="flex flex-col gap-2">
          <h2 className="flex justify-between text-small font-semibold text-muted">
            Check <span className="font-normal text-faint">pantry</span>
          </h2>
          <ul className="flex flex-wrap gap-1.5">
            {check.map((i) => (
              <li key={i.name} className="rounded-full border border-dashed border-line px-2.5 py-1 text-caption text-muted">
                {i.name}
                <span className="ml-1.5 text-faint">{i.text}</span>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  )
}

/** "500 g kippendijen, in reepjes" under a step; pantry ones fainter. */
export function StepIngredient({ ing, factor }: { ing: Ingredient; factor: number }) {
  return (
    <span className={cn(ing.pantry ? 'text-faint' : 'text-muted')}>
      <b className="font-semibold text-fg">{amountText(ing.amount, ing.unit, factor)}</b> {ing.name}
      {ing.note && `, ${ing.note}`}
    </span>
  )
}

function PhaseCard({ phase, factor }: { phase: Phase; factor: number }) {
  return (
    <Surface as="section" aria-label={`${phase.name}, ${phase.kind}`} padding="compact" className={cn('border-l-[3px]', phase.kind === 'prep' ? 'border-l-accent-fg' : 'border-l-cook')}>
      <div className="mb-2.5 flex items-baseline justify-between gap-3 px-1">
        <h3 className="text-title font-semibold">{phase.name}</h3>
        <span className={cn('text-label font-bold tracking-[0.12em] uppercase', phase.kind === 'prep' ? 'text-accent-fg' : 'text-cook')}>{phase.kind}</span>
      </div>
      <ol className="flex flex-col gap-3 px-1">
        {phase.steps.map((step, n) => (
          <li key={n} className="grid grid-cols-[1.25rem_minmax(0,1fr)] gap-2">
            <span className="pt-0.5 text-caption text-faint">{n + 1}</span>
            <span>
              <span className="block">{step.text}</span>
              {step.ingredients.length > 0 && (
                <span className="mt-1.5 flex flex-wrap gap-x-3 gap-y-1 text-caption">
                  {step.ingredients.map((ing) => (
                    <StepIngredient key={`${ing.name} ${ing.unit}`} ing={ing} factor={factor} />
                  ))}
                </span>
              )}
            </span>
          </li>
        ))}
      </ol>
    </Surface>
  )
}

/** The line between the last prep phase and the first cook phase: from here it is heat. */
export function Handover() {
  return (
    <div className="flex items-center gap-3" role="separator" aria-label="All prepped, now the heat">
      <span className="h-px flex-1 bg-linear-to-r from-accent-fg/60 to-cook/60" />
      <span className="flex items-center gap-1.5 text-small font-semibold text-cook">
        <Flame aria-hidden="true" className="size-4" />
        All prepped, now the heat
      </span>
      <span className="h-px flex-1 bg-linear-to-r from-accent-fg/60 to-cook/60" />
    </div>
  )
}

/** Every phase in order, with the handover line before the first cook phase. */
export function Phases({ recipe, factor }: { recipe: Recipe; factor: number }) {
  const handover = firstCook(recipe)
  return (
    <div className="flex flex-col gap-3.5">
      {recipe.phases.map((phase, i) => (
        <Fragment key={`${i} ${phase.name}`}>
          {i === handover && <Handover />}
          <PhaseCard phase={phase} factor={factor} />
        </Fragment>
      ))}
    </div>
  )
}
