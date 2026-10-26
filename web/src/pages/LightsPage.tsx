import { useEffect, useState } from 'react'
import { Loading, PageUnavailable, StaleNote } from '../components/ui/states'
import { FloorPlan } from '../components/lights/FloorPlan'
import { LightTile, type Change } from '../components/lights/LightTile'
import { PageHeader } from '../components/PageHeader'
import { Pill } from '../components/ui/Pill'
import { ApiError, sendJson } from '../lib/api'
import { cn } from '../lib/cn'
import { formatAgo } from '../lib/format'
import { applyIntent, HOLD_MS, pending, type Intent } from '../lib/lightIntent'
import type { LightsPlan } from '../lib/lightsPlan'
import type { Lights } from '../lib/types'
import { useApi } from '../lib/useApi'
import { buttonClass } from '../components/ui/buttonStyles'

/** While the page is open; the hub itself is kept live by the bridge's event stream. */
const REFRESH_MS = 2_000

/** The living room's lights through the Hue Bridge (plan.md M17), on its floor plan (M27, O). */
export function LightsPage() {
  const { data, error, loading, reload } = useApi<Lights>('/api/lights', REFRESH_MS)
  // The bridge's answer to our own change, until the next poll is newer.
  const [answer, setAnswer] = useState<Lights | null>(null)
  // What was just asked per group, shown at once until the bridge reports it.
  const [intents, setIntents] = useState<Record<string, Intent>>({})
  const [failure, setFailure] = useState<string | null>(null)
  const plan = useApi<LightsPlan>('/api/lights/plan')
  const [picked, setPicked] = useState<string | null>(null)

  const reported = answer && (!data || answer.as_of >= data.as_of) ? answer : data
  const lights = reported && { ...reported, groups: reported.groups.map((g) => applyIntent(g, intents[g.id])) }
  const total = lights?.groups.reduce((n, g) => n + g.lights.length, 0) ?? 0
  const on = lights?.groups.reduce((n, g) => n + g.lights.filter((l) => l.on).length, 0) ?? 0
  const disabled = !!lights?.stale

  // Let go of an intent once the bridge confirms it, or when it has waited too long.
  useEffect(() => {
    if (!reported || Object.keys(intents).length === 0) return
    const left = pending(intents, reported.groups, Date.now())
    const settled = Object.keys(left).length !== Object.keys(intents).length
    const next = settled ? 0 : Math.min(...Object.values(left).map((i) => i.until)) - Date.now()
    const timer = window.setTimeout(() => setIntents((now) => pending(now, reported.groups, Date.now())), Math.max(0, next))
    return () => window.clearTimeout(timer)
  }, [reported, intents])

  async function send(method: 'PUT' | 'POST', path: string, body: object, groupIds: string[], intent: Omit<Intent, 'until'>) {
    const until = Date.now() + HOLD_MS
    setIntents((now) => ({ ...now, ...Object.fromEntries(groupIds.map((id) => [id, { ...now[id], ...intent, until }])) }))
    setFailure(null)
    try {
      setAnswer(await sendJson<Lights>(method, path, body))
    } catch (err) {
      // Show what the bridge has, not what was asked.
      setIntents((now) => Object.fromEntries(Object.entries(now).filter(([id]) => !groupIds.includes(id))))
      setFailure(err instanceof ApiError ? err.message : 'The change did not reach the bridge.')
    } finally {
      reload()
    }
  }

  return (
    <>
      <PageHeader
        title="Lights"
        subtitle={lights ? `${lights.room} · through the Hue Bridge` : 'The living room through the Hue Bridge'}
        status={lights && <Pill tone={on ? 'accent' : 'muted'}>{on ? `${on} of ${total} on` : 'All off'}</Pill>}
      />

      {loading && !lights && (
        <Loading what="the lights" />
      )}
      {error && !lights && (
        <PageUnavailable what="The lights" plural detail="The hub reads them from the Hue Bridge every minute." />
      )}

      {lights && (
        <>
          <div className="mb-3.5 flex items-center justify-between gap-2.5">
            <p className="text-small text-muted">
              {lights.stale ? 'Last known state: the bridge is not answering right now.' : 'Changes from the switch, Siri or the Home app show here at once.'}
            </p>
            <button
              type="button"
              disabled={disabled}
              onClick={() =>
                send(
                  'POST',
                  '/api/lights/room',
                  { on: on === 0 },
                  lights.groups.map((g) => g.id),
                  { on: on === 0 },
                )
              }
              className={cn(buttonClass(), 'flex-none')}
            >
              {on ? 'All off' : 'All on'}
            </button>
          </div>
          <div className={cn('grid gap-3 md:gap-[18px]', plan.data && 'lg:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)]', lights.stale && 'opacity-60')}>
            {plan.data && (
              <figure className="m-0 self-start overflow-hidden rounded-[18px] border border-glass-line">
                <FloorPlan
                  plan={plan.data}
                  groups={lights.groups}
                  selected={picked}
                  onSelect={(id) => {
                    setPicked((now) => (now === id ? null : id))
                    document.getElementById(`lights-${id}`)?.scrollIntoView?.({ behavior: 'smooth', block: 'nearest' })
                  }}
                />
                <figcaption className="sr-only">Pick a light to find its group.</figcaption>
              </figure>
            )}
            <div
              className={cn('grid content-start gap-3 md:gap-[18px]', plan.data ? 'md:grid-cols-2 lg:grid-cols-1' : 'md:grid-cols-2')}
              aria-busy={Object.keys(intents).length > 0}
            >
              {lights.groups.map((group) => (
                <LightTile
                  key={group.id}
                  group={group}
                  kelvins={lights.kelvins}
                  disabled={disabled}
                  selected={picked === group.id}
                  onChange={(change: Change) => send('PUT', `/api/lights/${group.id}`, change, [group.id], change)}
                />
              ))}
            </div>
          </div>
          {failure && (
            <p role="alert" className="mt-3 text-small text-down">
              {failure}
            </p>
          )}
          {lights.stale && <StaleNote />}
          <p className="mt-3.5 text-caption text-faint">Updated {formatAgo(lights.as_of)} · Hue Bridge</p>
        </>
      )}
    </>
  )
}
