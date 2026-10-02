import { useSearchParams } from 'react-router'
import { PageHeader } from '../components/PageHeader'
import { StaleNote } from '../components/home/Card'
import { AllocationCard } from '../components/portfolio/AllocationCard'
import { HoldingView } from '../components/portfolio/HoldingView'
import { HoldingsCard } from '../components/portfolio/HoldingsCard'
import { MarketsCard } from '../components/portfolio/MarketsCard'
import { ValueCard } from '../components/portfolio/ValueCard'
import { cn } from '../lib/cn'
import { formatMoney, formatSignedMoney, formatSignedPct, formatWhen } from '../lib/format'
import { parseHolding } from '../lib/portfolio'
import type { PortfolioFull } from '../lib/portfolioTypes'
import { useApi } from '../lib/useApi'

const tone = (n: number | null | undefined) => (!n ? 'text-fg' : n > 0 ? 'text-up' : 'text-down')

/** The Ghostfolio portfolio; a holding's detail is `?h=<dataSource>/<symbol>`. */
export function PortfolioPage() {
  const [params] = useSearchParams()
  const selected = parseHolding(params.get('h'))
  const { data, error } = useApi<PortfolioFull>('/api/portfolio', 300_000)

  if (selected)
    return <HoldingView dataSource={selected.dataSource} symbol={selected.symbol} currency={data?.currency ?? 'EUR'} />

  if (!data)
    return (
      <>
        <PageHeader title="Portfolio" />
        {error ? (
          <p className="text-muted">The portfolio is not available right now. Ghostfolio may be down.</p>
        ) : (
          <p role="status" className="text-muted">
            Loading…
          </p>
        )}
      </>
    )

  const money = (n: number) => formatMoney(n, data.currency)
  // The sum of the holdings' moves, like the daily report, so it matches the table.
  const dayAbs = data.holdings.reduce((sum, h) => sum + (h.day_abs ?? 0), 0)
  const dayPct = data.total_value - dayAbs ? (dayAbs / (data.total_value - dayAbs)) * 100 : 0
  const summary: [string, string, string, string?][] = [
    ['Today', formatSignedMoney(dayAbs, data.currency), formatSignedPct(dayPct), tone(dayAbs)],
    [
      'Total gain',
      data.gain_abs != null ? formatSignedMoney(data.gain_abs, data.currency) : '–',
      formatSignedPct(data.change.all_pct),
      tone(data.gain_abs),
    ],
    ['Invested', data.invested != null ? money(data.invested) : '–', ''],
    ['Cash', data.cash != null ? money(data.cash) : '–', data.dividends ? `${money(data.dividends)} dividends` : ''],
  ]

  return (
    <>
      <PageHeader title="Portfolio" subtitle={`From Ghostfolio, ${formatWhen(data.as_of)}`} />

      <section aria-label="Summary" className="mb-4 rounded-[14px] border border-line-soft bg-card px-5 py-5 md:px-6">
        <p className="text-[13px] font-semibold text-muted">Value</p>
        <p className="text-[32px] font-semibold tracking-tight md:text-[38px]">{money(data.total_value)}</p>
        <dl className="mt-3 grid grid-cols-2 gap-x-6 gap-y-3 sm:grid-cols-4">
          {summary.map(([label, value, detail, colour]) => (
            <div key={label}>
              <dt className="text-[12px] text-faint">{label}</dt>
              <dd className={cn('font-semibold', colour)}>
                {value}
                {detail && <span className="ml-1.5 text-[12.5px] font-normal opacity-80">{detail}</span>}
              </dd>
            </div>
          ))}
        </dl>
        {data.stale && <StaleNote />}
      </section>

      <div className="grid gap-4 lg:grid-cols-[minmax(0,2fr)_minmax(0,1fr)]">
        <div className="min-w-0 space-y-4">
          <ValueCard currency={data.currency} />
          <HoldingsCard holdings={data.holdings} currency={data.currency} />
        </div>
        <div className="min-w-0 space-y-4">
          <AllocationCard allocation={data.allocation} />
          <MarketsCard />
        </div>
      </div>
    </>
  )
}
