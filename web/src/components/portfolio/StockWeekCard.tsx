import { Shuffle } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router'
import { cn } from '../../lib/cn'
import { formatSignedPct } from '../../lib/format'
import { holdingPath } from '../../lib/portfolio'
import type { HoldingRow } from '../../lib/portfolioTypes'
import { formatPrice, pickAnother, weekView, type StockWeeks } from '../../lib/stockWeek'
import { useApi } from '../../lib/useApi'
import { iconButtonClass } from '../ui/buttonStyles'
import { Card } from '../ui/Card'
import { Pill } from '../ui/Pill'
import { Loading, StaleNote, Unavailable } from '../ui/states'
import { WeekChart } from './WeekChart'

/** One holding's last five trading days, as on the House panel (decided 2026-11-06, in place of
 * the movers heat map): a random holding each visit, the shuffle for another. */
export function StockWeekCard({ holdings, random = Math.random }: { holdings: HoldingRow[]; random?: () => number }) {
  const { data, error } = useApi<StockWeeks>('/api/portfolio/weeks', 900_000)
  // Where the first pick falls, drawn once per visit.
  const [seed] = useState(random)
  const [chosen, setChosen] = useState<string | null>(null)

  const owned = new Map(holdings.map((h) => [h.symbol, h]))
  const weeks = (data?.stocks ?? [])
    .filter((s) => owned.has(s.symbol))
    .map((s) => ({ stock: s, holding: owned.get(s.symbol)!, view: weekView(s) }))
    .filter((w) => w.view)

  if (!data)
    return (
      <Card title="This week">
        {error ? <Unavailable what="The week's prices" plural detail="Yahoo may not be answering." /> : <Loading what="the week" />}
      </Card>
    )
  if (!weeks.length)
    return (
      <Card title="This week">
        <p className="text-muted">No week of prices for your holdings yet.</p>
        {data.stale && <StaleNote />}
      </Card>
    )

  const found = weeks.findIndex((w) => w.stock.symbol === chosen)
  const index = found >= 0 ? found : Math.min(weeks.length - 1, Math.floor(seed * weeks.length))
  const { stock, holding, view } = weeks[index]
  const week = view!
  const up = week.change >= 0
  const shuffle = () => setChosen(weeks[pickAnother(weeks.length, index, random)].stock.symbol)

  return (
    <Card
      title="This week"
      actions={
        weeks.length > 1 && (
          <button type="button" onClick={shuffle} aria-label="Show another holding" title="Another holding" className={iconButtonClass}>
            <Shuffle aria-hidden="true" className="size-4" />
          </button>
        )
      }
    >
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0">
          <Link to={holdingPath(holding)} className="text-page leading-tight font-semibold hover:underline">
            {stock.symbol}
          </Link>
          <p className="truncate text-small text-muted">{holding.name}</p>
        </div>
        <div className="shrink-0 text-right">
          <p className={cn('text-display leading-tight font-semibold', up ? 'text-up' : 'text-down')}>{formatSignedPct(week.change)}</p>
          <p className="text-small text-muted">{formatPrice(stock.price, stock.currency)}</p>
        </div>
      </div>
      <div className="mt-3 mb-4 flex flex-wrap gap-2">
        <Pill tone={holding.day_pct >= 0 ? 'up' : 'down'}>{formatSignedPct(holding.day_pct)} today</Pill>
        {holding.gain_pct != null && (
          <Pill tone={holding.gain_pct >= 0 ? 'up' : 'down'}>Yours {formatSignedPct(holding.gain_pct)}</Pill>
        )}
      </div>
      <WeekChart key={stock.symbol} stock={stock} view={week} />
      {data.stale && <StaleNote />}
    </Card>
  )
}
