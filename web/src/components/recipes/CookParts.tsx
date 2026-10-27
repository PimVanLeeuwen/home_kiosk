import { Check, Flame } from 'lucide-react'
import { cn } from '../../lib/cn'
import { phaseDone } from '../../lib/cookProgress'
import { amountText } from '../../lib/recipes'
import type { Recipe, Step } from '../../lib/recipeTypes'

type Kind = 'prep' | 'cook'

const ON = { prep: 'border-accent-fg bg-accent-fg text-canvas', cook: 'border-cook bg-cook text-canvas' }

function Tick({ on, kind, small }: { on: boolean; kind: Kind; small?: boolean }) {
  return (
    <span
      aria-hidden="true"
      className={cn('grid shrink-0 place-items-center rounded-full border-2', small ? 'size-[22px]' : 'size-7', on ? ON[kind] : 'border-line')}
    >
      {on && <Check className={small ? 'size-3' : 'size-4'} strokeWidth={3} />}
    </span>
  )
}

/** A step still to do: large text, what goes in it, and a big tick. Later steps are dimmed. */
export function CookStepCard({ step, kind, factor, now, onTick }: { step: Step; kind: Kind; factor: number; now: boolean; onTick: () => void }) {
  return (
    <button
      type="button"
      aria-pressed={false}
      onClick={onTick}
      className={cn(
        'pressable grid w-full grid-cols-[1.75rem_minmax(0,1fr)] gap-3.5 rounded-[18px] border bg-card p-4 text-left',
        now ? (kind === 'prep' ? 'border-accent-line/45 bg-accent/10' : 'border-cook/45 bg-cook/8') : 'border-line-soft opacity-55',
      )}
    >
      <Tick on={false} kind={kind} />
      <span className="flex flex-col gap-3">
        <span className={cn('leading-snug text-fg', now ? 'text-heading' : 'text-title')}>{step.text}</span>
        {step.ingredients.length > 0 && (
          <span className="grid grid-cols-[auto_minmax(0,1fr)] gap-x-3 gap-y-1.5 text-title">
            {step.ingredients.map((ing) => (
              <span key={`${ing.name} ${ing.unit}`} className="contents">
                <b className={cn('text-right font-semibold whitespace-nowrap', ing.pantry ? 'text-muted' : 'text-fg')}>{amountText(ing.amount, ing.unit, factor)}</b>
                <span className={ing.pantry ? 'text-faint' : 'text-muted'}>
                  {ing.name}
                  {ing.note && `, ${ing.note}`}
                </span>
              </span>
            ))}
          </span>
        )}
      </span>
    </button>
  )
}

/** A ticked step, folded to one line; a tap unticks it. */
export function DoneLine({ step, kind, onTick }: { step: Step; kind: Kind; onTick: () => void }) {
  return (
    <button type="button" aria-pressed onClick={onTick} className="flex w-full items-center gap-3 rounded-[12px] bg-glass px-3.5 py-2.5 text-left text-faint">
      <Tick on kind={kind} small />
      <s className="line-clamp-1 decoration-white/25">{step.text}</s>
    </button>
  )
}

/** One segment per phase in its colour: filled as far as its steps are ticked. */
export function PhaseBar({ recipe, ticks, current }: { recipe: Recipe; ticks: string[]; current: number | null }) {
  return (
    <div className="flex gap-1" aria-hidden="true">
      {recipe.phases.map((phase, i) => {
        const share = phaseDone(recipe, ticks, i) / phase.steps.length
        return (
          <span key={i} className={cn('h-[5px] flex-1 overflow-hidden rounded-full bg-raised', i === current && 'outline outline-1 outline-offset-1 outline-line')}>
            <span className={cn('block h-full rounded-full', phase.kind === 'prep' ? 'bg-accent-fg' : 'bg-cook')} style={{ width: `${share * 100}%` }} />
          </span>
        )
      })}
    </div>
  )
}

/** Between the last prep phase and the first cook phase: what is ready, and what comes first. */
export function Pause({ recipe, ticks }: { recipe: Recipe; ticks: string[] }) {
  const firstCook = recipe.phases.findIndex((p) => p.kind === 'cook')
  const first = recipe.phases[firstCook]
  return (
    <div className="flex flex-col items-center gap-4 pt-2 text-center">
      <span className="grid size-28 place-items-center rounded-full bg-[radial-gradient(circle,color-mix(in_srgb,var(--color-cook)_35%,transparent),transparent_68%)]">
        <span className="grid size-[68px] place-items-center rounded-full border border-cook/50 bg-canvas text-cook">
          <Flame aria-hidden="true" className="size-8" />
        </span>
      </span>
      <h1 className="text-page font-semibold">All prepped</h1>
      <p className="max-w-[30ch] text-muted">Everything is cut, mixed and set apart. From here it is heat and timing.</p>
      <ul aria-label="Prep" className="flex w-full flex-col gap-2">
        {recipe.phases.slice(0, firstCook).map((phase, i) => {
          const done = phaseDone(recipe, ticks, i)
          const all = done === phase.steps.length
          return (
            <li key={i} className="flex items-center gap-3 rounded-[12px] border border-line-soft bg-card px-3.5 py-2.5 text-left">
              <Check aria-hidden="true" className={cn('size-4', all ? 'text-accent-fg' : 'text-faint')} />
              {phase.name}
              <span className={cn('ml-auto text-caption', all ? 'text-faint' : 'text-warn')}>
                {all ? `${phase.steps.length} ${phase.steps.length === 1 ? 'step' : 'steps'}` : `${done} of ${phase.steps.length} ticked`}
              </span>
            </li>
          )
        })}
      </ul>
      <div className="w-full rounded-[14px] border border-cook/30 bg-cook/10 p-3.5 text-left">
        <p className="text-label font-bold tracking-[0.12em] text-cook uppercase">First, {first.name}</p>
        <p className="mt-1">{first.steps[0].text}</p>
      </div>
    </div>
  )
}
