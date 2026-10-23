import { cn } from '../../lib/cn'
import { formatSignedPct } from '../../lib/format'
import type { Indices } from '../../lib/portfolioTypes'
import { useApi } from '../../lib/useApi'
import { Card } from '../ui/Card'
import { StaleNote } from '../ui/states'

const decimals = new Intl.NumberFormat('nl-NL', { minimumFractionDigits: 2, maximumFractionDigits: 2 })

/** The index line from the daily report. */
export function MarketsCard() {
  const { data } = useApi<Indices>('/api/indices', 900_000)
  if (!data?.indices.length) return null
  return (
    <Card
      title="Markets"
      actions={<span className="text-[11px] font-semibold tracking-[0.08em] text-faint uppercase">Last session</span>}
    >
      <ul className="grid gap-2 text-[13.5px]">
        {data.indices.map((q) => (
          // Read in order: name, level, move; the move is placed at the right.
          <li
            key={q.symbol}
            className="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-x-3 rounded-[11px] border border-glass-line bg-glass px-3 py-2.5"
          >
            <span className="col-start-1 row-start-1 truncate">{q.label}</span>
            <span className="col-start-1 row-start-2 text-[12px] text-muted">{decimals.format(q.price)}</span>
            <span
              className={cn(
                'col-start-2 row-span-2 row-start-1 rounded-[7px] px-1.5 py-0.5 text-[12.5px] font-semibold',
                q.day_pct > 0 ? 'bg-up/12 text-up' : q.day_pct < 0 ? 'bg-down/13 text-down' : 'bg-raised text-muted',
              )}
            >
              {formatSignedPct(q.day_pct)}
            </span>
          </li>
        ))}
      </ul>
      {data.stale && <StaleNote />}
    </Card>
  )
}
