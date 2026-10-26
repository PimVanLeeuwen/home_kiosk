import { useState } from 'react'
import { sendJson } from '../../lib/api'
import { PIECE_KINDS, PIECE_LABEL, PIECE_SIZE, type LightsPlan, type PieceKind } from '../../lib/lightsPlan'
import type { Lights } from '../../lib/types'
import { useApi } from '../../lib/useApi'
import { FloorPlan, type Placed } from '../lights/FloorPlan'
import { Surface } from '../ui/Card'
import { Loading, Unavailable } from '../ui/states'
import { buttonClass, primaryButtonClass } from './fields'

/**
 * The Lights page's floor plan, placed once (plan.md M27, O): the room's
 * proportions, where each light hangs and a few furniture outlines, dragged
 * into place (or moved with the arrow keys). Nothing changes on the bridge.
 */
export function LightsPlanEditor() {
  const lights = useApi<Lights>('/api/lights')
  const stored = useApi<LightsPlan>('/api/lights/plan')
  const [draft, setDraft] = useState<LightsPlan | null>(null)
  const [active, setActive] = useState<number | null>(null)
  const [status, setStatus] = useState<{ saved?: boolean; error?: string }>({})
  const plan = draft ?? stored.data

  if (!plan || !lights.data) {
    return lights.error || stored.error ? <Unavailable what="The lights" plural /> : <Loading />
  }

  const change = (next: LightsPlan) => {
    setDraft(next)
    setStatus({})
  }

  function place(what: Placed, at: { x: number; y: number }) {
    if (!plan) return
    if ('light' in what) {
      change({ ...plan, lights: { ...plan.lights, [what.light]: at } })
    } else {
      setActive(what.piece)
      change({ ...plan, furniture: plan.furniture.map((p, i) => (i === what.piece ? { ...p, ...at } : p)) })
    }
  }

  function toggle(kind: PieceKind) {
    if (!plan) return
    const has = plan.furniture.some((p) => p.kind === kind)
    setActive(null)
    change({
      ...plan,
      furniture: has ? plan.furniture.filter((p) => p.kind !== kind) : [...plan.furniture, { kind, x: 0.5, y: 0.5, ...PIECE_SIZE[kind] }],
    })
  }

  function turn() {
    if (!plan || active === null) return
    change({ ...plan, furniture: plan.furniture.map((p, i) => (i === active ? { ...p, w: p.h, h: p.w } : p)) })
  }

  async function save() {
    if (!plan) return
    try {
      const saved = await sendJson<LightsPlan>('PUT', '/api/lights/plan', plan)
      setDraft(saved)
      setStatus({ saved: true })
    } catch (err) {
      setStatus({ error: err instanceof Error ? err.message : String(err) })
    }
  }

  const unsaved = draft !== null && !status.saved

  return (
    <Surface>
      <p className="mb-3 text-caption text-faint">
        The living room from above, for the Lights page. Drag each light to where it hangs and the furniture to where it stands, or pick one and use the arrow keys.
      </p>
      <div className="overflow-hidden rounded-[14px] border border-glass-line">
        <FloorPlan plan={plan} groups={lights.data.groups} onPlace={place} activePiece={active} />
      </div>

      <div className="mt-4 grid gap-4 sm:grid-cols-2">
        <label className="grid gap-1.5 text-small">
          <span className="text-muted">
            Room shape: {plan.aspect.toFixed(1)} times as wide as deep
          </span>
          <input
            type="range"
            min={1}
            max={3}
            step={0.1}
            value={plan.aspect}
            onChange={(e) => change({ ...plan, aspect: Number(e.target.value) })}
            className="accent-(--color-accent)"
          />
        </label>
        <fieldset className="grid gap-1.5 text-small">
          <legend className="mb-1.5 text-muted">Furniture</legend>
          <div className="flex flex-wrap gap-2">
            {PIECE_KINDS.map((kind) => {
              const shown = plan.furniture.some((p) => p.kind === kind)
              return (
                <button key={kind} type="button" aria-pressed={shown} onClick={() => toggle(kind)} className={shown ? primaryButtonClass : buttonClass}>
                  {PIECE_LABEL[kind]}
                </button>
              )
            })}
            <button type="button" disabled={active === null} onClick={turn} className={buttonClass}>
              Turn {active !== null ? PIECE_LABEL[plan.furniture[active]?.kind ?? 'sofa'].toLowerCase() : 'it'}
            </button>
          </div>
        </fieldset>
      </div>

      <div className="mt-4 flex flex-wrap items-center gap-3">
        <button type="button" disabled={!unsaved} onClick={save} className={primaryButtonClass}>
          Save the plan
        </button>
        <button
          type="button"
          disabled={!unsaved}
          onClick={() => {
            setDraft(null)
            setActive(null)
          }}
          className={buttonClass}
        >
          Undo changes
        </button>
        {status.saved && (
          <p role="status" className="text-small text-up">
            Saved: the Lights page shows it now.
          </p>
        )}
        {status.error && (
          <p role="alert" className="text-small text-down">
            {status.error}
          </p>
        )}
      </div>
    </Surface>
  )
}
