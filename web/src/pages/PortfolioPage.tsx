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
import { formatMoney, formatSignedMoney, formatSignedPct, formatWhen } from '../lib/format'
import { dayMove, parseHolding } from '../lib/portfolio'
import type { PortfolioFull } from '../lib/portfolioTypes'
import { useApi } from '../lib/useApi'
import { buttonClass } from '../components/ui/buttonStyles'
import { Pill } from '../components/ui/Pill'
import { StatTile, StatTiles } from '../components/ui/StatTile'
import type { Tone } from '../components/ui/tones'
import { AnimatedNumber } from '../components/ui/AnimatedNumber'

const tone = (n: number | null | undefined): Tone | undefined => (!n ? undefined : n > 0 ? 'up' : 'down')

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
  const signed = (n: number) => formatSignedMoney(n, data.currency)
  // Label, amount (moving to a new value on a refresh), how it is written, the line below, its colour.
  const summary: [string, number | null | undefined, (n: number) => string, string, Tone?][] = [
    ['Today', dayAbs, signed, formatSignedPct(dayPct), tone(dayAbs)],
    ['Total gain', data.gain_abs, signed, formatSignedPct(data.change.all_pct), tone(data.gain_abs)],
    ['Invested', data.invested, money, ''],
    ['Cash', data.cash, money, data.dividends ? `${money(data.dividends)} dividends` : ''],
  ]

  return (
    <>
      <PageHeader
        title="Portfolio"
        subtitle={`From Ghostfolio, ${formatWhen(data.as_of)}`}
        status={<Pill tone={dayPct > 0 ? 'up' : dayPct < 0 ? 'down' : 'muted'}>{formatSignedPct(dayPct)} today</Pill>}
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

      <ValueCard currency={data.currency} total={data.total_value} />
      {data.stale && <StaleNote />}

      <div className="mt-5">
        <StatTiles label="Summary" count={4}>
          {summary.map(([label, value, format, detail, colour]) => (
            <StatTile
              key={label}
              title={label}
              figure={value != null ? <AnimatedNumber value={value} format={format} /> : '–'}
              sub={detail || undefined}
              tone={colour}
            />
          ))}
        </StatTiles>
      </div>

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
