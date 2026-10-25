import { formatAgo, formatCount } from '../../lib/format'
import type { DnsStats } from '../../lib/types'
import { AnimatedNumber } from '../ui/AnimatedNumber'
import { BarStrip } from '../ui/BarStrip'
import { Card } from '../ui/Card'
import { RingMeter } from '../ui/RingMeter'
import { Loading, StaleNote, Unavailable } from '../ui/states'

interface Props {
  data: DnsStats | undefined
  error: Error | undefined
}

/** Why nothing is blocked right now, when that is so. */
function problem(dns: DnsStats): string | null {
  if (!dns.answering && dns.failing === 'dns')
    return 'AdGuard does not answer lookups: the house looks names up through Quad9, without blocking.'
  if (!dns.answering) return 'AdGuard is not answering: the house looks names up through Quad9, without blocking. Showing its last figures.'
  if (!dns.protection) return 'Blocking is paused in AdGuard: every ad gets through until it is switched back on.'
  return null
}

/**
 * Ad and tracker blocking for the whole house, from AdGuard Home (plan.md M24):
 * the last 24 hours as counts, the hourly blocks and the most-blocked domain.
 * Never which device asked for what.
 */
export function DnsCard({ data: dns, error }: Props) {
  const now = new Date()
  const trouble = dns && problem(dns)
  return (
    <Card title="Ad blocking" actions={<span className="text-caption text-muted">Last 24 hours</span>}>
      {!dns && (error ? <Unavailable what="AdGuard Home" /> : <Loading />)}
      {dns && (
        <>
          {trouble && (
            <p role="status" className="mb-4 text-small text-warn">
              {trouble}
            </p>
          )}
          <div className="grid grid-cols-[minmax(0,1fr)_96px] items-center gap-4 sm:grid-cols-[minmax(0,1fr)_112px]">
            <div className="min-w-0">
              <p className="text-giant leading-none font-semibold tracking-tight tabular-nums">
                <AnimatedNumber value={dns.blocked} format={(n) => formatCount(Math.round(n))} />
              </p>
              <p className="mt-2 text-small text-muted">
                blocked of <span className="font-semibold text-fg">{formatCount(dns.queries)}</span> lookups
              </p>
            </div>
            {dns.share != null && (
              <RingMeter pct={dns.share} tone={trouble ? 'warn' : 'accent'} label={`${Math.round(dns.share)}% of lookups blocked`} caption="blocked" />
            )}
          </div>
          {dns.hours.length > 1 && (
            <div className="mt-5">
              <BarStrip
                values={dns.hours.map((h) => h.blocked)}
                label="Blocked lookups per hour, the last 24 hours"
                tone={trouble ? 'warn' : 'accent'}
                start="24 h ago"
                end="now"
                height={48}
              />
            </div>
          )}
          {dns.top_blocked && (
            <p className="mt-4 flex min-w-0 items-baseline justify-between gap-3 text-small">
              <span className="shrink-0 text-muted">Most blocked</span>
              <span className="min-w-0 truncate font-mono text-fg" title={dns.top_blocked}>
                {dns.top_blocked}
                {dns.top_blocked_count != null && <span className="ml-2 font-sans text-faint">{formatCount(dns.top_blocked_count)}×</span>}
              </span>
            </p>
          )}
          <p className="mt-3 text-caption text-faint">Updated {formatAgo(dns.as_of, now)} · AdGuard Home</p>
          {dns.stale && !trouble && <StaleNote />}
        </>
      )}
    </Card>
  )
}
