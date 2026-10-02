import { useState } from 'react'
import { cn } from '../../lib/cn'
import { formatMoney, formatSignedMoney } from '../../lib/format'
import type { ChartRange, PortfolioHistory } from '../../lib/portfolioTypes'
import { useApi } from '../../lib/useApi'
import { Card, Loading, Unavailable } from '../home/Card'
import { FilterPill } from '../news/FilterPill'
import { LineChart } from './LineChart'

const RANGES: [ChartRange, string, string][] = [
  ['month', '1M', 'Gain over the last month'],
  ['ytd', 'YTD', 'Gain this year'],
  ['year', '1Y', 'Gain over the last year'],
  ['max', 'Max', 'Gain since the start'],
]

/** Value over time with what was put in; the gain leaves deposits out. */
export function ValueCard({ currency }: { currency: string }) {
  const [range, setRange] = useState<ChartRange>('year')
  const { data, error } = useApi<PortfolioHistory>(`/api/portfolio/history?range=${range}`)
  const points = data?.range === range ? data.points : undefined
  const [, short, gainLabel] = RANGES.find(([r]) => r === range)!

  const first = points?.[0]
  const last = points?.at(-1)
  // Value change minus new money in: what the investments themselves did.
  const gain =
    first && last && first.invested != null && last.invested != null
      ? last.v - last.invested - (first.v - first.invested)
      : null

  const money = (n: number) => formatMoney(n, currency)
  return (
    <Card
      title="Value"
      actions={
        <div role="group" aria-label="Period" className="flex gap-1">
          {RANGES.map(([r, label]) => (
            <FilterPill key={r} on={range === r} onClick={() => setRange(r)}>
              {label}
            </FilterPill>
          ))}
        </div>
      }
    >
      {!points && (error ? <Unavailable what="The value history" /> : <Loading />)}
      {points && (
        <>
          {gain != null && (
            <p className="mb-3 text-[13px] text-muted">
              {gainLabel}:{' '}
              <span className={cn('font-semibold', gain > 0 ? 'text-up' : gain < 0 ? 'text-down' : 'text-fg')}>
                {formatSignedMoney(gain, currency)}
              </span>{' '}
              <span className="text-faint">(deposits and withdrawals left out)</span>
            </p>
          )}
          <LineChart
            points={points.map((p) => ({ d: p.d, a: p.v, b: p.invested }))}
            aLabel="Value"
            bLabel="Invested"
            format={money}
            label={`Portfolio value, ${short}: from ${money(first!.v)} to ${money(last!.v)}.`}
          />
        </>
      )}
    </Card>
  )
}
