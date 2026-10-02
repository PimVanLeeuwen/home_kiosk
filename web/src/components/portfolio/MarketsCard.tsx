import { cn } from '../../lib/cn'
import { formatSignedPct } from '../../lib/format'
import type { Indices } from '../../lib/portfolioTypes'
import { useApi } from '../../lib/useApi'
import { Card, StaleNote } from '../home/Card'

const decimals = new Intl.NumberFormat('nl-NL', { minimumFractionDigits: 2, maximumFractionDigits: 2 })

/** The index line from the daily report. */
export function MarketsCard() {
  const { data } = useApi<Indices>('/api/indices', 900_000)
  if (!data?.indices.length) return null
  return (
    <Card title="Markets">
      <ul className="space-y-2 text-[13.5px]">
        {data.indices.map((q) => (
          <li key={q.symbol} className="flex items-baseline gap-3">
            <span className="min-w-0 flex-1 truncate whitespace-nowrap">{q.label}</span>
            <span className="text-[12.5px] text-muted">{decimals.format(q.price)}</span>
            <span className={cn('w-16 text-right font-medium', q.day_pct > 0 ? 'text-up' : q.day_pct < 0 ? 'text-down' : 'text-muted')}>
              {formatSignedPct(q.day_pct)}
            </span>
          </li>
        ))}
      </ul>
      <p className="mt-3 text-[12px] text-faint">Last session's move.</p>
      {data.stale && <StaleNote />}
    </Card>
  )
}
