import { useState } from 'react'
import { cn } from '../../lib/cn'
import { formatMoney, formatSignedMoney, formatSignedPct } from '../../lib/format'
import type { ChartRange, PortfolioHistory } from '../../lib/portfolioTypes'
import { useApi } from '../../lib/useApi'
import { Card, Loading, Unavailable } from '../home/Card'
import { Pill } from '../ui/Pill'
import { Segmented } from '../ui/Segmented'
import { LineChart } from './LineChart'

const RANGES: [ChartRange, string, string][] = [
  ['month', '1M', 'Gain over the last month'],
  ['ytd', 'YTD', 'Gain this year'],
  ['year', '1Y', 'Gain over the last year'],
  ['max', 'Max', 'Gain since the start'],
]

interface Props {
  currency: string
  /** The value now, large, with today's move as a pill beside it. */
  total: number
  todayPct: number
}

/** The portfolio's value now and over time with what was put in; the gain leaves deposits out. */
export function ValueCard({ currency, total, todayPct }: Props) {
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
      className="pb-0 md:pb-0"
      actions={<Segmented label="Period" options={RANGES.map(([r, label]) => [r, label])} value={range} onChange={setRange} />}
    >
      <p className="-mt-1 flex flex-wrap items-baseline gap-x-3 gap-y-1">
        <span className="text-[31px] leading-tight font-semibold tracking-tight md:text-[38px]">{money(total)}</span>
        <Pill tone={todayPct > 0 ? 'up' : todayPct < 0 ? 'down' : 'muted'}>{formatSignedPct(todayPct)} today</Pill>
      </p>
      {!points && <div className="pb-5">{error ? <Unavailable what="The value history" /> : <Loading />}</div>}
      {points && (
        <>
          {gain != null && (
            <p className="mt-1 mb-3 text-[13px] text-muted">
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
            bleed
          />
        </>
      )}
    </Card>
  )
}
