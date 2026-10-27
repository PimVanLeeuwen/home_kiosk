import { ChevronLeft, ChevronRight, Flame, Sun, SunDim, X } from 'lucide-react'
import { useEffect, useMemo, useState, type ReactNode } from 'react'
import { createPortal } from 'react-dom'
import { Link, useNavigate, useParams, useSearchParams } from 'react-router'
import { CookStepCard, DoneLine, Pause, PhaseBar } from '../components/recipes/CookParts'
import { Button } from '../components/ui/Button'
import { Loading, PageUnavailable } from '../components/ui/states'
import { cn } from '../lib/cn'
import { cookViews, loadCook, saveCook, stepKey, toggleTick, type CookState } from '../lib/cookProgress'
import type { Recipe, RecipeDetail } from '../lib/recipeTypes'
import { useApi } from '../lib/useApi'
import { useWakeLock } from '../lib/useWakeLock'

/** Over the whole hub, tab bar included: while cooking only the recipe is on screen. */
const LAYER = 'fixed inset-0 z-40 flex flex-col bg-panel'

/**
 * Straight into the body: the page area has a view-transition name, which makes it a stacking
 * context of its own, so from inside it no z-index gets above the tab bar.
 */
const Layer = ({ children }: { children: ReactNode }) => createPortal(children, document.body)

/** Cook mode (plan.md M30): one phase at a time, ticks kept on the phone for the day. */
export function CookPage() {
  const id = useParams().id ?? ''
  const { data, error, reload } = useApi<RecipeDetail>(`/api/recipes/${encodeURIComponent(id)}`)
  if (!data) {
    return (
      <Layer>
        <div className={cn(LAYER, 'p-5')}>
          {error ? <PageUnavailable what="This recipe" detail={error.message} onRetry={reload} /> : <Loading what="the recipe" />}
        </div>
      </Layer>
    )
  }
  return <Cook key={`${id} ${data.updated_at}`} detail={data} />
}

function Cook({ detail }: { detail: RecipeDetail }) {
  const { recipe } = detail
  const navigate = useNavigate()
  const [params] = useSearchParams()
  const persons = Math.min(50, Math.max(1, Number(params.get('persons')) || recipe.servings))
  const factor = persons / recipe.servings
  const views = useMemo(() => cookViews(recipe), [recipe])
  const [state, setState] = useState<CookState>(() => loadCook(recipe.id, detail.updated_at, views.length))
  const wake = useWakeLock()
  const back = `/recipes/${encodeURIComponent(recipe.id)}${persons !== recipe.servings ? `?persons=${persons}` : ''}`

  useEffect(() => saveCook(recipe.id, state), [recipe.id, state])
  useEffect(() => {
    document.title = `Cooking ${recipe.title} · Home hub`
    const escape = (e: KeyboardEvent) => e.key === 'Escape' && navigate(back, { viewTransition: true })
    window.addEventListener('keydown', escape)
    return () => window.removeEventListener('keydown', escape)
  }, [recipe.title, navigate, back])

  const view = views[state.view]
  const go = (step: number) =>
    setState((s) => ({
      ...s,
      view: Math.min(Math.max(s.view + step, 0), views.length - 1),
    }))
  const last = state.view === views.length - 1
  const phaseIndex = view.kind === 'phase' ? view.phase : null
  const nextView = views[state.view + 1]
  const nextName = nextView && (nextView.kind === 'pause' ? 'All prepped' : recipe.phases[nextView.phase].name)

  return (
    <Layer>
      <div className={LAYER} role="dialog" aria-modal aria-label={`Cooking ${recipe.title}`}>
        <div className="mx-auto flex w-full max-w-2xl flex-1 flex-col gap-4 overflow-y-auto px-[max(1.1rem,env(safe-area-inset-left))] pt-[max(1rem,env(safe-area-inset-top))] pb-40">
          <div className="flex items-center justify-between gap-3">
            <Link
              to={back}
              viewTransition
              aria-label="Close cook mode"
              className="grid size-10 place-items-center rounded-[12px] border border-line-soft bg-card text-muted hover:text-fg"
            >
              <X aria-hidden="true" className="size-5" />
            </Link>
            <span className="flex items-center gap-1.5 text-caption text-faint">
              {wake === 'on' ? (
                <span className="flex items-center gap-1.5 text-up">
                  <Sun aria-hidden="true" className="size-4" />
                  Screen on
                </span>
              ) : (
                <span className="flex items-center gap-1.5">
                  <SunDim aria-hidden="true" className="size-4" />
                  Screen may sleep
                </span>
              )}
              · {persons} {persons === 1 ? 'person' : 'persons'}
            </span>
          </div>
          <PhaseBar recipe={recipe} ticks={state.ticks} current={phaseIndex} />

          {view.kind === 'pause' ? (
            <Pause recipe={recipe} ticks={state.ticks} />
          ) : (
            <PhaseSteps recipe={recipe} phase={view.phase} factor={factor} ticks={state.ticks} onTick={(key) => setState((s) => toggleTick(s, key))} />
          )}
          {nextName && view.kind === 'phase' && <p className="text-label font-bold tracking-[0.12em] text-faint uppercase">Next: {nextName}</p>}
        </div>

        <div className="fixed inset-x-0 bottom-0 bg-linear-to-b from-transparent to-panel to-30% pt-8 pb-[max(1.25rem,env(safe-area-inset-bottom))]">
          <div className="mx-auto flex max-w-2xl flex-col gap-2.5 px-[max(1.1rem,env(safe-area-inset-left))]">
            {view.kind === 'pause' ? (
              <>
                <Button variant="heat" onClick={() => go(1)} className="h-12 text-title">
                  <Flame aria-hidden="true" className="size-5" />
                  Start cooking
                </Button>
                <Button onClick={() => go(-1)} className="h-11">
                  Back to prep
                </Button>
              </>
            ) : (
              <div className="flex gap-2.5">
                {state.view > 0 && (
                  <Button aria-label="Previous phase" onClick={() => go(-1)} className="h-12 w-14">
                    <ChevronLeft aria-hidden="true" className="size-5" />
                  </Button>
                )}
                {last ? (
                  <Button variant="primary" onClick={() => navigate(back, { viewTransition: true })} className="h-12 flex-1 text-title">
                    Done
                  </Button>
                ) : (
                  <Button onClick={() => go(1)} className="h-12 flex-1 text-title">
                    {nextView?.kind === 'pause' ? 'All prepped' : 'Next phase'}
                    <ChevronRight aria-hidden="true" className="size-5" />
                  </Button>
                )}
              </div>
            )}
          </div>
        </div>
      </div>
    </Layer>
  )
}

function PhaseSteps({
  recipe,
  phase,
  factor,
  ticks,
  onTick,
}: {
  recipe: Recipe
  phase: number
  factor: number
  ticks: string[]
  onTick: (key: string) => void
}) {
  const current = recipe.phases[phase]
  const ofKind = recipe.phases.filter((p) => p.kind === current.kind)
  const position = ofKind.indexOf(current) + 1
  const firstOpen = current.steps.findIndex((_, s) => !ticks.includes(stepKey(phase, s)))
  return (
    <section aria-label={current.name} className="flex flex-col gap-3">
      <div>
        <p className={cn('text-label font-bold tracking-[0.12em] uppercase', current.kind === 'prep' ? 'text-accent-fg' : 'text-cook')}>
          {current.kind} {position} of {ofKind.length}
        </p>
        <h1 className="text-hero leading-tight font-semibold tracking-tight">{current.name}</h1>
      </div>
      {current.steps.map((step, s) => {
        const key = stepKey(phase, s)
        return ticks.includes(key) ? (
          <DoneLine key={key} step={step} kind={current.kind} onTick={() => onTick(key)} />
        ) : (
          <CookStepCard key={key} step={step} kind={current.kind} factor={factor} now={s === firstOpen} onTick={() => onTick(key)} />
        )
      })}
      {firstOpen === -1 && <p className="text-small text-up">All done in this phase.</p>}
    </section>
  )
}
