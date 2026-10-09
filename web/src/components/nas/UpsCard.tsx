import { Card, StaleNote } from '../home/Card'
import { Meter } from '../home/Meter'
import { cn } from '../../lib/cn'
import { formatWhen } from '../../lib/format'
import type { Ups, UpsOutage } from '../../lib/types'
import { useApi } from '../../lib/useApi'

const STATUS = {
  online: { label: 'On mains', className: 'text-up' },
  on_battery: { label: 'On battery', className: 'text-warn' },
  low_battery: { label: 'Low battery', className: 'text-down' },
  unknown: { label: 'Unknown', className: 'text-muted' },
} as const

function minutes(o: UpsOutage): string {
  const total = Math.max(1, Math.round((new Date(o.ended_at!).getTime() - new Date(o.started_at).getTime()) / 60_000))
  return total >= 60 ? `${Math.floor(total / 60)} h ${total % 60} min` : `${total} min`
}

function describe(o: UpsOutage): string {
  const lowest = o.lowest_charge != null ? `, down to ${o.lowest_charge}%` : ''
  return `${formatWhen(o.started_at)}, ${minutes(o)}${lowest}${o.reached_low ? ' (services stopped)' : ''}`
}

/** The UPS from UGOS's NUT server: state, battery and the last power cuts. Hidden when not set up. */
export function UpsCard() {
  const { data: ups } = useApi<Ups>('/api/ups', 15_000)
  if (!ups) return null

  const status = STATUS[ups.status]
  const current = ups.outages.find((o) => !o.ended_at)
  const past = ups.outages.filter((o) => o.ended_at).slice(0, 3)

  return (
    <Card title="UPS">
      <dl className="mb-4 grid grid-cols-[auto_minmax(0,1fr)] gap-x-4 gap-y-1.5 text-[13.5px]">
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
      </dl>
      {ups.charge != null && (
        <Meter
          label="Battery"
          value={`${ups.charge}%`}
          pct={ups.charge}
          tone={ups.status === 'low_battery' ? 'down' : ups.status === 'on_battery' ? 'warn' : 'ok'}
        />
      )}
      <div className="mt-4 text-[12.5px] text-muted">
        <p className="text-faint">Power cuts</p>
        {past.length === 0 ? (
          <p>None recorded.</p>
        ) : (
          <ul className="mt-1 space-y-0.5">
            {past.map((o) => (
              <li key={o.started_at}>{describe(o)}</li>
            ))}
          </ul>
        )}
        <p className="mt-2">
          At {ups.charge_low ?? 15}% UGOS stops all services. Telegram gets one message per power cut once the internet
          is back.
        </p>
      </div>
      {ups.stale && <StaleNote />}
    </Card>
  )
}
