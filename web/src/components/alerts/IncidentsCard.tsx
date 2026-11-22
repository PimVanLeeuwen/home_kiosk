import { useState } from 'react'
import { ApiError } from '../../lib/api'
import { cn } from '../../lib/cn'
import { formatWhen } from '../../lib/format'
import { lasted, setDismissed, weekOf } from '../../lib/incidents'
import type { Incident } from '../../lib/types'
import { Card } from '../ui/Card'
import { buttonClass } from '../ui/buttonStyles'
import { Loading } from '../ui/states'
import { Pill } from '../ui/Pill'

function Week({ incidents, now, className }: { incidents: Incident[]; now: Date; className?: string }) {
  const days = weekOf(incidents, now)
  return (
    <ol aria-label="The last 7 days" className={cn('flex gap-2.5', className)}>
      {days.map((d, i) => (
        <li key={i} className="grid justify-items-center gap-1 text-label text-faint">
          <b
            data-worst={d.worst ?? 'none'}
            className={cn(
              'block size-[9px] rounded-full',
              d.worst === 'error' && 'bg-down shadow-glow shadow-down',
              d.worst === 'warning' && 'bg-warn shadow-glow shadow-warn',
              !d.worst && 'bg-up/50',
              d.today && 'outline outline-offset-2 outline-white/35',
            )}
          />
          <span aria-hidden="true">{d.label}</span>
          <span className="sr-only">{d.worst ? `${d.worst} that day` : 'quiet that day'}</span>
        </li>
      ))}
    </ol>
  )
}

const ICON = (
  <svg viewBox="0 0 24 24" className="size-[22px]" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" aria-hidden="true">
    <rect x="3" y="5" width="18" height="14" rx="2.5" />
    <path d="M3 14h18" />
    <circle cx="17" cy="16.5" r=".9" fill="currentColor" />
  </svg>
)

interface Props {
  incidents: Incident[] | undefined
  now: Date
  /** After a dismissal or an undo: read the incidents again. */
  onChange?: () => void
}

/**
 * What is open now, each with Dismiss until it resolves, or "All quiet" with slow ripples and the
 * last seven days; the dismissed ones still open sit below, with Undo.
 */
export function IncidentsCard({ incidents, now, onChange }: Props) {
  const [failed, setFailed] = useState<string>()
  const open = (incidents ?? []).filter((i) => !i.resolved_at && !i.dismissed_at)
  const dismissed = (incidents ?? []).filter((i) => !i.resolved_at && i.dismissed_at)
  async function toggle(incident: Incident, dismiss: boolean) {
    setFailed(undefined)
    try {
      await setDismissed(incident.key, dismiss)
    } catch (err) {
      setFailed(err instanceof ApiError ? err.message : 'That did not work; try again.')
    }
    onChange?.()
  }
  const lastEnd = Math.max(0, ...(incidents ?? []).map((i) => (i.resolved_at ? new Date(i.resolved_at).getTime() : 0)))

  return (
    <Card
      title="Open alerts"
    >
      {!incidents && <Loading />}
      {incidents && open.length === 0 && (
        <div className="grid justify-items-center text-center">
          <div className="relative grid size-[120px] place-items-center" aria-hidden="true">
            {[0, 1.2, 2.4].map((delay) => (
              <i
                key={delay}
                className="absolute inset-[22px] rounded-full border border-up/45 motion-safe:animate-ripple motion-reduce:hidden"
                style={{ animationDelay: `${delay}s` }}
              />
            ))}
            <svg viewBox="0 0 60 60" className="w-16">
              <circle cx="30" cy="30" r="22" fill="color-mix(in srgb, var(--color-up) 14%, transparent)" stroke="color-mix(in srgb, var(--color-up) 50%, transparent)" strokeWidth="1.4" />
              <path d="M21 30.5l6 6 12-13" fill="none" stroke="var(--color-up)" strokeWidth="3.2" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </div>
          <p className="mt-1 text-heading font-semibold">All quiet</p>
          <p className="text-small text-muted">
            {lastEnd ? `Nothing has needed you for ${lasted(now.getTime() - lastEnd)}` : 'Nothing has needed you yet'}
          </p>
          <Week incidents={incidents} now={now} className="mt-3 justify-center" />
        </div>
      )}
      {open.length > 0 && (
        <>
          <ul className="grid gap-2">
            {open.map((i) => {
              const error = i.severity === 'error'
              return (
                <li
                  key={i.key}
                  className={cn(
                    'grid grid-cols-[44px_minmax(0,1fr)] items-start gap-3 rounded-tile border p-3.5',
                    error ? 'border-down/40 bg-linear-to-br from-down/14 to-down/[0.03]' : 'border-warn/35 bg-linear-to-br from-warn/13 to-warn/[0.03]',
                  )}
                >
                  <span
                    className={cn(
                      'grid size-11 place-items-center rounded-tile border border-white/12 bg-white/6 motion-safe:animate-halo',
                      error ? 'text-down [--glow:var(--color-down)]' : 'text-warn [--glow:var(--color-warn)]',
                    )}
                  >
                    {ICON}
                  </span>
                  <div className="min-w-0">
                    <div className="flex items-start justify-between gap-2">
                      <Pill tone={error ? 'down' : i.severity === 'warning' ? 'warn' : 'accent'}>{i.severity}</Pill>
                      <button
                        type="button"
                        aria-label={`Dismiss: ${i.title}`}
                        title="Dismiss until it resolves"
                        onClick={() => toggle(i, true)}
                        className="hit -mt-0.5 text-small font-medium text-muted hover:text-fg"
                      >
                        Dismiss
                      </button>
                    </div>
                    <p className="mt-1 text-title leading-snug font-semibold">{i.title}</p>
                    {i.body && <p className="mt-0.5 text-small text-muted">{i.body}</p>}
                    <p className="mt-0.5 text-small text-faint">
                      open {lasted(now.getTime() - new Date(i.opened_at).getTime())} · since {formatWhen(i.opened_at, now)}
                    </p>
                  </div>
                </li>
              )
            })}
          </ul>
          <div className="mt-3.5 flex items-end">
            <Week incidents={incidents!} now={now} />
            <span className="ml-auto text-label text-faint">last 7 days</span>
          </div>
        </>
      )}
      {dismissed.length > 0 && (
        <div className="mt-4 border-t border-line-soft pt-3.5">
          <p className="text-label eyebrow text-faint">Dismissed until they resolve</p>
          <ul aria-label="Dismissed" className="mt-1.5">
            {dismissed.map((i) => (
              <li key={i.key} className="flex items-center gap-3 py-1.5 text-small">
                <span className="min-w-0 flex-1 truncate text-muted">{i.title}</span>
                <button type="button" onClick={() => toggle(i, false)} className={buttonClass('secondary', 'sm')}>
                  Undo
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}
      {failed && (
        <p role="alert" className="mt-3 text-small text-down">
          {failed}
        </p>
      )}
    </Card>
  )
}
