import { formatSignedPct } from '../../lib/format'
import type { Indices } from '../../lib/portfolioTypes'
import { useApi } from '../../lib/useApi'
import { Card } from '../ui/Card'
import { StaleNote } from '../ui/states'
import { Tag } from '../ui/Tag'

const decimals = new Intl.NumberFormat('nl-NL', { minimumFractionDigits: 2, maximumFractionDigits: 2 })

/** The index line from the daily report. */
export function MarketsCard() {
  const { data } = useApi<Indices>('/api/indices', 900_000)
  if (!data?.indices.length) return null
  return (
    <Card
      title="Markets"
      note="Last session"
    >
      <ul className="grid gap-2 text-small">
        {data.indices.map((q) => (
          // Read in order: name, level, move; the move is placed at the right.
          <li
            key={q.symbol}
            className="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-x-3 rounded-tile border border-glass-line bg-glass px-3 py-2.5"
          >
            <span className="col-start-1 row-start-1 truncate">{q.label}</span>
            <span className="col-start-1 row-start-2 text-small text-muted">{decimals.format(q.price)}</span>
            <Tag tone={q.day_pct > 0 ? 'up' : q.day_pct < 0 ? 'down' : 'muted'} size="caption" className="col-start-2 row-span-2 row-start-1">
              {formatSignedPct(q.day_pct)}
            </Tag>
          </li>
        ))}
      </ul>
      {data.stale && <StaleNote />}
    </Card>
  )
}
