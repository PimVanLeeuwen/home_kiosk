import { Card } from '../ui/Card'
import { StaleNote } from '../ui/states'
import { cn } from '../../lib/cn'
import { formatWhen } from '../../lib/format'
import type { Ups, UpsOutage } from '../../lib/types'
import { useApi } from '../../lib/useApi'
import { Pill } from '../ui/Pill'
import { RingMeter } from '../ui/RingMeter'
import type { Tone } from '../ui/tones'

const STATUS: Record<Ups['status'], { label: string; tone: Tone; className: string }> = {
  online: { label: 'On mains', tone: 'up', className: 'text-up' },
  on_battery: { label: 'On battery', tone: 'warn', className: 'text-warn' },
  low_battery: { label: 'Low battery', tone: 'down', className: 'text-down' },
  unknown: { label: 'Unknown', tone: 'muted', className: 'text-muted' },
}

function minutes(o: UpsOutage): string {
  const total = Math.max(1, Math.round((new Date(o.ended_at!).getTime() - new Date(o.started_at).getTime()) / 60_000))
  return total >= 60 ? `${Math.floor(total / 60)} h ${total % 60} min` : `${total} min`
}

function describe(o: UpsOutage): string {
  const lowest = o.lowest_charge != null ? `, down to ${o.lowest_charge}%` : ''
  return `${formatWhen(o.started_at)}, ${minutes(o)}${lowest}${o.reached_low ? ' (services stopped)' : ''}`
}

/** The UPS from UGOS's NUT server: the battery as a ring, its state, and the last power cuts. Hidden when not set up. */
export function UpsCard() {
  const { data: ups } = useApi<Ups>('/api/ups', 15_000)
  if (!ups) return null

  const status = STATUS[ups.status]
  const current = ups.outages.find((o) => !o.ended_at)
  const past = ups.outages.filter((o) => o.ended_at).slice(0, 3)

  return (
    <Card title="UPS" actions={<Pill tone={status.tone}>{status.label}</Pill>}>
      <div className="grid grid-cols-[110px_minmax(0,1fr)] items-center gap-4 sm:grid-cols-[130px_minmax(0,1fr)] sm:gap-5">
        {ups.charge != null ? (
          <RingMeter pct={ups.charge} tone={status.tone} label="Battery" caption="battery" />
        ) : (
          <span />
        )}
        <dl className="grid grid-cols-[auto_minmax(0,1fr)] gap-x-4 gap-y-1 text-[13.5px]">
          <dt className="text-muted">Status</dt>
          <dd>
            <span className={cn('font-semibold', status.className)}>{status.label}</span>
            {current && <span className="text-muted"> since {formatWhen(current.started_at)}</span>}
          </dd>
          <dt className="text-muted">Load</dt>
          <dd>{ups.load != null ? `${ups.load}%` : '–'}</dd>
          {ups.model && (
            <>
              <dt className="text-muted">Model</dt>
              <dd>{ups.model}</dd>
            </>
          )}
          <dt className="text-muted">Stops at</dt>
          <dd>{ups.charge_low ?? 15}%</dd>
        </dl>
      </div>

      <p className="mt-4 text-[11px] font-semibold tracking-[0.08em] text-faint uppercase">Power cuts</p>
      {past.length === 0 ? (
        <p className="mt-1 text-[12.5px] text-muted">None recorded.</p>
      ) : (
        <ol className="mt-2 grid gap-2 border-l border-line pl-3.5 text-[12.5px]">
          {past.map((o) => (
            <li key={o.started_at} className="relative">
              <span
                aria-hidden="true"
                className={cn(
                  'absolute top-[0.45em] -left-[18px] size-[7px] rounded-full',
                  o.reached_low ? 'bg-down shadow-[0_0_8px_var(--color-down)]' : 'bg-faint',
                )}
              />
              <span className={o.reached_low ? 'text-fg' : 'text-muted'}>{describe(o)}</span>
            </li>
          ))}
        </ol>
      )}
      <p className="mt-3 text-[12px] text-faint">
        At {ups.charge_low ?? 15}% UGOS stops all services. Telegram gets one message per power cut once the internet is
        back.
      </p>
      {ups.stale && <StaleNote />}
    </Card>
  )
}
