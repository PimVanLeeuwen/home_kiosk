import type { CSSProperties } from 'react'
import { cn } from '../../lib/cn'
import { formatTime } from '../../lib/format'
import { followed, minutesToGo, trainShows, trainStatus } from '../../lib/train'
import type { Train, TrainRun } from '../../lib/types'
import { TONE_COLOR } from '../ui/tones'
import { Card } from '../ui/Card'
import { StaleNote } from '../ui/states'

const R = 26
const C = 2 * Math.PI * R

/** Minutes to go as a ring that empties over the last hour. */
function MinutesRing({ minutes, color, label }: { minutes: number; color: string; label: string }) {
  const filled = Math.min(1, minutes / 60)
  return (
    <svg role="img" aria-label={`${minutes} ${label}`} viewBox="0 0 64 64" className="w-[76px] shrink-0 md:w-24">
      <circle cx="32" cy="32" r={R} fill="none" stroke="rgb(255 255 255 / 0.08)" strokeWidth="4.5" />
      <circle
        cx="32"
        cy="32"
        r={R}
        fill="none"
        stroke={color}
        strokeWidth="4.5"
        strokeLinecap="round"
        className="motion-safe:animate-sweep"
        strokeDasharray={`${(C * filled).toFixed(1)} ${C.toFixed(1)}`}
        transform="rotate(-90 32 32)"
        style={{ filter: `drop-shadow(0 0 3px ${color})` }}
      />
      <text x="32" y="33" textAnchor="middle" fontSize="16" fontWeight="600" fill="var(--color-fg)">
        {minutes}
      </text>
      <text x="32" y="44" textAnchor="middle" fontSize="6.5" fill="var(--color-muted)">
        {label}
      </text>
    </svg>
  )
}

function Platform({ run }: { run: TrainRun }) {
  const changed = run.planned_track && run.actual_track && run.planned_track !== run.actual_track
  return (
    <>
      platform{' '}
      {changed && <s className="text-faint">{run.planned_track}</s>}{' '}
      <span
        data-changed={changed || undefined}
        className={cn(
          'rounded-[6px] px-1.5 font-semibold',
          changed
            ? 'bg-warn/15 text-warn shadow-[0_0_0_1px_--alpha(var(--color-warn)/40%),0_0_14px_-2px_--alpha(var(--color-warn)/60%)]'
            : 'bg-raised text-fg',
        )}
      >
        {run.actual_track ?? run.planned_track ?? '?'}
      </span>
    </>
  )
}

/**
 * The weekday morning train at the top of Home, the hub's view of the Now
 * panel's card: shown from 06:00 until it has left, and the evening before
 * only when tomorrow's train has a problem. Hidden the rest of the time.
 */
export function TrainCard({ data }: { data: Train | undefined }) {
  const now = new Date()
  if (!trainShows(data, now)) return null

  const train = data
  const run = train.train
  const evening = train.mode === 'evening'
  const status = trainStatus(train)
  const color = TONE_COLOR[status.tone]
  const gone = !run || run.status === 'cancelled' || run.status === 'not_found'
  const next = followed(train)
  const destination = run?.stops.at(-1)?.name ?? train.route.split(' to ').at(-1)
  const late = run?.status === 'late'

  let sub
  if (gone) sub = `The ${train.departure} to ${destination} does not run${evening ? ' tomorrow' : ''}`
  else if (evening) sub = <>Tomorrow at {train.departure} from <Platform run={run} /></>
  else {
    const minutes = minutesToGo(run, now)
    sub = minutes < 1 ? <>Leaves now from <Platform run={run} /></> : <>Leaves in {minutes} min from <Platform run={run} /></>
  }

  const ring = !evening && next && (
    <MinutesRing minutes={minutesToGo(next, now)} color={color} label={gone ? 'min to next' : 'min to go'} />
  )

  return (
    <Card title={`${evening ? "Tomorrow's train" : 'Your train'} · direct · ${train.route}`} className="mb-5">
      <div
        aria-hidden="true"
        style={{ '--glow': color } as CSSProperties}
        className="pointer-events-none absolute inset-0 bg-[radial-gradient(55%_90%_at_92%_0%,color-mix(in_srgb,var(--glow)_16%,transparent),transparent_70%)]"
      />
      <div className="relative grid grid-cols-[minmax(0,1fr)_auto] items-center gap-4 md:grid-cols-[auto_minmax(0,1fr)_auto] md:gap-7">
        <div className="rounded-[12px] border border-glass-line bg-glass px-3.5 pt-2.5 pb-3 md:min-w-32">
          <span className="block text-label font-semibold tracking-[0.08em] text-faint uppercase">Departure</span>
          <span className="text-display leading-tight font-semibold tracking-tight">
            {gone ? (
              <s className="text-faint">{train.departure}</s>
            ) : late && run.actual_departure ? (
              <>
                <s className="mr-1.5 text-[0.55em] font-medium text-faint">{train.departure}</s>
                {formatTime(run.actual_departure)}
              </>
            ) : (
              train.departure
            )}
          </span>
        </div>
        <div className="col-span-2 row-start-2 min-w-0 md:col-span-1 md:row-start-auto">
          <p data-tone={status.tone} className="text-stat leading-tight font-semibold tracking-tight md:text-page" style={{ color }}>
            {status.word}
          </p>
          <p className="mt-1 text-muted">{sub}</p>
        </div>
        {ring && <div className="col-start-2 row-start-1 md:col-start-auto md:row-start-auto">{ring}</div>}
      </div>

      {gone && train.next_direct && (
        <div className="relative mt-4 flex flex-wrap items-baseline gap-x-3.5 gap-y-1 rounded-[12px] border border-glass-line bg-glass px-3.5 py-3">
          <span className="basis-full text-label font-semibold tracking-[0.08em] text-faint uppercase">Next direct train</span>
          <span className="text-stat font-semibold">{formatTime(train.next_direct.planned_departure)}</span>
          <span>
            <Platform run={train.next_direct} />
            {train.next_direct.stops.length > 0 && (
              <span className="text-muted"> · arrives {formatTime(train.next_direct.stops.at(-1)!.actual ?? train.next_direct.stops.at(-1)!.planned)}</span>
            )}
          </span>
        </div>
      )}

      {run && run.stops.length > 0 && (
        <ol
          aria-label="Stops"
          style={{ '--line': color } as CSSProperties}
          className={cn(
            'relative mt-5 grid grid-cols-1 md:grid-cols-4',
            'before:absolute before:top-1.5 before:bottom-3.5 before:left-[5px] before:w-0.5 before:bg-linear-to-b before:from-(--line) before:to-white/8',
            'md:before:top-[5px] md:before:right-[12%] md:before:bottom-auto md:before:left-1.5 md:before:h-0.5 md:before:w-auto md:before:bg-linear-to-r',
            gone && 'opacity-40',
          )}
        >
          {run.stops.map((stop, i) => {
            const at = stop.actual ?? stop.planned
            const shifted = !gone && stop.actual && stop.actual !== stop.planned
            return (
              <li key={stop.name} className="relative grid grid-cols-[48px_1fr] gap-x-2.5 pb-2.5 pl-[22px] md:block md:p-0 md:pt-[18px]">
                <b
                  className={cn(
                    'absolute top-px left-0 size-3 rounded-full border-2 md:top-0',
                    i === 0 && !gone ? 'border-(--line) bg-(--line) shadow-[0_0_10px_var(--line)]' : 'border-white/25 bg-card',
                  )}
                />
                <span className={cn('font-mono text-small', shifted && 'text-warn', (gone || stop.cancelled) && 'line-through')}>
                  {formatTime(at)}
                </span>
                <span className={cn('truncate text-small text-muted md:block', stop.cancelled && 'line-through')}>{stop.name}</span>
              </li>
            )
          })}
        </ol>
      )}

      {train.disruptions.map((d) => (
        <div key={d.id} role="note" className="relative mt-4 flex items-start gap-2.5 rounded-[10px] border border-warn/35 bg-warn/8 px-3 py-2.5 text-small">
          <span aria-hidden="true" className="mt-1.5 size-2 shrink-0 rounded-full bg-warn shadow-[0_0_8px_var(--color-warn)]" />
          <p>
            <b className="text-warn">{d.title}</b> <span className="text-muted">{[d.text, d.until].filter(Boolean).join(' ')} (NS)</span>
          </p>
        </div>
      ))}

      {train.stale && <StaleNote />}
    </Card>
  )
}
