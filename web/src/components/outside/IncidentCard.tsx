import { ExternalLink } from 'lucide-react'
import { formatTime, formatWhen } from '../../lib/format'
import { runningFor, STATE_LABEL, STATE_TEXT, statusWord } from '../../lib/outside'
import type { OutsideIncident, OutsideService } from '../../lib/types'
import { cn } from '../../lib/cn'
import { BrandLogo } from './BrandLogo'

const FRAME: Record<OutsideIncident['impact'], string> = {
  outage: 'border-down/40 bg-linear-to-br from-down/12 to-down/[0.03]',
  degraded: 'border-warn/35 bg-linear-to-br from-warn/12 to-warn/[0.03]',
  maintenance: 'border-line bg-raised/60',
}

/** Today's updates by their time, older ones with the day. */
const when = (iso: string, now: Date) =>
  new Date(iso).toDateString() === now.toDateString() ? formatTime(iso) : formatWhen(iso, now)

interface Props {
  service: OutsideService
  incident: OutsideIncident
  now?: Date
}

/** One incident: the service with a pulsing halo, how bad and how long, the
 * latest word from the status page, and its timeline (newest first). */
export function IncidentCard({ service, incident, now = new Date() }: Props) {
  const latest = incident.updates.at(-1)
  const since = runningFor(incident.started_at, now)
  const timeline = [...incident.updates].reverse()
  const state = incident.impact === 'maintenance' ? 'maintenance' : incident.impact
  return (
    <article
      aria-label={`${service.name}: ${incident.title}`}
      className={cn('grid gap-3 rounded-[12px] border p-4', FRAME[incident.impact])}
    >
      <header className="flex items-center gap-3">
        <BrandLogo service={service} size={40} halo={incident.impact !== 'maintenance'} />
        <div className="min-w-0">
          <p className="text-[15px] leading-tight font-semibold">
            {service.name}: {incident.title}
          </p>
          <p className="mt-0.5 text-[12.5px] text-muted">
            <span className={STATE_TEXT[state]}>{STATE_LABEL[state]}</span>
            {since && <> · {since}</>}
          </p>
        </div>
      </header>
      {latest?.text && <p className="text-[13.5px] leading-snug">{latest.text}</p>}
      {timeline.length > 0 && (
        <ol aria-label="Timeline" className="grid gap-1.5 border-l border-line pl-3">
          {timeline.map((u, i) => (
            <li key={u.at + u.status} className="relative flex items-baseline gap-2 text-[12.5px]">
              <span
                aria-hidden="true"
                className={cn(
                  'absolute top-[0.45em] -left-[16.5px] size-[7px] rounded-full',
                  i === 0 ? 'bg-fg shadow-[0_0_0_3px_--alpha(var(--color-fg)/12%)]' : 'bg-faint',
                )}
              />
              <span className={i === 0 ? 'font-medium' : 'text-muted'}>{statusWord(u.status)}</span>
              <span className="text-faint">{when(u.at, now)}</span>
            </li>
          ))}
        </ol>
      )}
      {incident.url && (
        <a
          href={incident.url}
          target="_blank"
          rel="noreferrer"
          className="inline-flex w-fit items-center gap-1.5 text-[12.5px] font-medium text-accent-fg hover:underline"
        >
          On the status page
          <ExternalLink aria-hidden="true" className="size-3.5" />
        </a>
      )}
    </article>
  )
}
