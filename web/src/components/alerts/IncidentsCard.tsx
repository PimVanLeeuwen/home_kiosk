import { cn } from '../../lib/cn'
import { formatWhen } from '../../lib/format'
import { lasted, weekOf } from '../../lib/incidents'
import type { Incident } from '../../lib/types'
import { Card } from '../ui/Card'
import { Loading } from '../ui/states'
import { Pill } from '../ui/Pill'

function Week({ incidents, now, className }: { incidents: Incident[]; now: Date; className?: string }) {
  const days = weekOf(incidents, now)
  return (
    <ol aria-label="The last 7 days" className={cn('flex gap-2.5', className)}>
      {days.map((d, i) => (
        <li key={i} className="grid justify-items-center gap-1 text-[10.5px] text-faint">
          <b
            data-worst={d.worst ?? 'none'}
            className={cn(
              'block size-[9px] rounded-full',
              d.worst === 'error' && 'bg-down shadow-[0_0_6px_var(--color-down)]',
              d.worst === 'warning' && 'bg-warn shadow-[0_0_6px_var(--color-warn)]',
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

/** What is open now, or "All quiet" with slow ripples and the last seven days. */
export function IncidentsCard({ incidents, now }: { incidents: Incident[] | undefined; now: Date }) {
  const open = (incidents ?? []).filter((i) => !i.resolved_at)
  const lastEnd = Math.max(0, ...(incidents ?? []).map((i) => (i.resolved_at ? new Date(i.resolved_at).getTime() : 0)))

  return (
    <Card
      title="Open alerts"
      actions={incidents && (open.length ? <Pill tone="down">{open.length} open</Pill> : <Pill tone="up">None open</Pill>)}
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
              <circle cx="30" cy="30" r="22" fill="rgb(63 185 127 / 0.14)" stroke="rgb(63 185 127 / 0.5)" strokeWidth="1.4" />
              <path d="M21 30.5l6 6 12-13" fill="none" stroke="var(--color-up)" strokeWidth="3.2" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </div>
          <p className="mt-1 text-[20px] font-semibold">All quiet</p>
          <p className="text-[12.5px] text-muted">
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
                    'grid grid-cols-[44px_minmax(0,1fr)] items-start gap-3 rounded-[12px] border p-3.5',
                    error ? 'border-down/40 bg-linear-to-br from-down/14 to-down/[0.03]' : 'border-warn/35 bg-linear-to-br from-warn/13 to-warn/[0.03]',
                  )}
                >
                  <span
                    className={cn(
                      'grid size-11 place-items-center rounded-[12px] border border-white/12 bg-white/6 motion-safe:animate-halo',
                      error ? 'text-down [--glow:var(--color-down)]' : 'text-warn [--glow:var(--color-warn)]',
                    )}
                  >
                    {ICON}
                  </span>
                  <div className="min-w-0">
                    <Pill tone={error ? 'down' : i.severity === 'warning' ? 'warn' : 'accent'}>{i.severity}</Pill>
                    <p className="mt-1 text-[16px] leading-snug font-semibold">{i.title}</p>
                    {i.body && <p className="mt-0.5 text-[12px] text-muted">{i.body}</p>}
                    <p className="mt-0.5 text-[12px] text-faint">
                      open {lasted(now.getTime() - new Date(i.opened_at).getTime())} · since {formatWhen(i.opened_at, now)}
                    </p>
                  </div>
                </li>
              )
            })}
          </ul>
          <div className="mt-3.5 flex items-end">
            <Week incidents={incidents!} now={now} />
            <span className="ml-auto text-[11px] text-faint">last 7 days</span>
          </div>
        </>
      )}
    </Card>
  )
}
