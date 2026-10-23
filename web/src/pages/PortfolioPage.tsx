import { FileUp } from 'lucide-react'
import { Link, useSearchParams } from 'react-router'
import { PageHeader } from '../components/PageHeader'
import { Loading, StaleNote, Unavailable } from '../components/ui/states'
import { AllocationCard } from '../components/portfolio/AllocationCard'
import { DegiroImport } from '../components/portfolio/DegiroImport'
import { HoldingView } from '../components/portfolio/HoldingView'
import { HoldingsCard } from '../components/portfolio/HoldingsCard'
import { MoversCard } from '../components/portfolio/MoversCard'
import { MarketsCard } from '../components/portfolio/MarketsCard'
import { ValueCard } from '../components/portfolio/ValueCard'
import { cn } from '../lib/cn'
import { formatMoney, formatSignedMoney, formatSignedPct, formatWhen } from '../lib/format'
import { dayMove, parseHolding } from '../lib/portfolio'
import type { PortfolioFull } from '../lib/portfolioTypes'
import { useApi } from '../lib/useApi'
import { buttonClass } from '../components/ui/buttonStyles'

const tone = (n: number | null | undefined) => (!n ? 'text-fg' : n > 0 ? 'text-up' : 'text-down')

/** The Ghostfolio portfolio; a holding's detail is `?h=<dataSource>/<symbol>`. */
export function PortfolioPage() {
  const [params] = useSearchParams()
  const selected = parseHolding(params.get('h'))
  const { data, error, reload } = useApi<PortfolioFull>('/api/portfolio', 300_000)

  // The collector refreshes from Ghostfolio right after an import; give it a moment.
  if (params.has('import')) return <DegiroImport onImported={() => window.setTimeout(reload, 8000)} />

  if (selected)
    return <HoldingView dataSource={selected.dataSource} symbol={selected.symbol} currency={data?.currency ?? 'EUR'} />

  if (!data)
    return (
      <>
        <PageHeader title="Portfolio" />
        {error ? (
          <Unavailable what="The portfolio" detail="Ghostfolio may be down." />
        ) : (
          <Loading />
        )}
      </>
    )

  const money = (n: number) => formatMoney(n, data.currency)
  // The sum of the holdings' moves, like the daily report, so it matches the table.
  const { abs: dayAbs, pct: dayPct } = dayMove(data)
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
      <PageHeader
        title="Portfolio"
        subtitle={`From Ghostfolio, ${formatWhen(data.as_of)}`}
        actions={
          <Link
            to="/portfolio?import"
            aria-label="Update from DEGIRO"
            className={buttonClass()}
          >
            <FileUp aria-hidden="true" className="size-4" />
            <span className="hidden sm:inline">Update from DEGIRO</span>
            <span className="sm:hidden">DEGIRO</span>
          </Link>
        }
      />

      <ValueCard currency={data.currency} total={data.total_value} todayPct={dayPct} />
      {data.stale && <StaleNote />}

      <section aria-label="Summary" className="my-5">
        <dl className="grid grid-cols-2 gap-2.5 md:gap-4 xl:grid-cols-4">
          {summary.map(([label, value, detail, colour]) => (
            <div
              key={label}
              className="rounded-[14px] border border-line-soft bg-card bg-linear-to-b from-white/[0.03] to-white/[0.01] px-4 py-3.5"
            >
              <dt className="text-[12.5px] text-muted">{label}</dt>
              <dd className={cn('mt-0.5 text-[16px] font-semibold md:text-[19px]', colour)}>
                {value}
                {detail && <span className="block text-[12px] font-normal text-muted">{detail}</span>}
              </dd>
            </div>
          ))}
        </dl>
      </section>

      <div className="grid gap-4 lg:grid-cols-[minmax(0,2fr)_minmax(0,1fr)]">
        <div className="min-w-0 space-y-4">
          <MoversCard holdings={data.holdings} />
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
