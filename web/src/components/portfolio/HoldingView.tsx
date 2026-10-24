import { ChevronLeft } from 'lucide-react'
import { Link } from 'react-router'
import { cn } from '../../lib/cn'
import { formatDate, formatMoney, formatPrice, formatQuantity, formatSignedMoney, formatSignedPct } from '../../lib/format'
import type { HoldingDetail } from '../../lib/portfolioTypes'
import { useApi } from '../../lib/useApi'
import { PageHeader } from '../PageHeader'
import { Card } from '../ui/Card'
import { Pill } from '../ui/Pill'
import { LineChart } from './LineChart'
import { Loading, Unavailable } from '../ui/states'

const TYPES: Record<string, string> = {
  BUY: 'Buy',
  SELL: 'Sell',
  DIVIDEND: 'Dividend',
  FEE: 'Fee',
  INTEREST: 'Interest',
  LIABILITY: 'Liability',
}

/** A colour per transaction type for its dot and chip; money in green, costs amber. */
const TYPE_COLOURS: Record<string, string> = {
  BUY: 'var(--color-accent-line)',
  SELL: 'var(--color-data-blue)',
  DIVIDEND: 'var(--color-up)',
  INTEREST: 'var(--color-up)',
  FEE: 'var(--color-warn)',
  LIABILITY: 'var(--color-down)',
}

interface Props {
  dataSource: string
  symbol: string
  currency: string
}

/** One holding: figures, its price against your average price, and its transactions. */
export function HoldingView({ dataSource, symbol, currency }: Props) {
  const { data, error } = useApi<HoldingDetail>(
    `/api/portfolio/holdings/${dataSource}/${encodeURIComponent(symbol)}`,
  )
  const back = (
    <Link to="/portfolio" className="mb-4 inline-flex items-center gap-1 text-small text-accent-fg hover:underline">
      <ChevronLeft aria-hidden="true" className="size-4" />
      Portfolio
    </Link>
  )

  if (!data)
    return (
      <>
        {back}
        <PageHeader title={symbol} />
        {error ? (
          <Unavailable what="This holding" />
        ) : (
          <Loading />
        )}
      </>
    )

  const own = data.currency ?? currency
  const gainTone = !data.gain_abs ? 'text-fg' : data.gain_abs > 0 ? 'text-up' : 'text-down'
  const figures: [string, string, string?][] = [
    ['Value', formatMoney(data.value, currency)],
    [
      'Gain',
      data.gain_abs != null
        ? `${formatSignedMoney(data.gain_abs, currency)}${data.gain_pct != null ? ` · ${formatSignedPct(data.gain_pct)}` : ''}`
        : '–',
      gainTone,
    ],
    ['Quantity', formatQuantity(data.quantity)],
    ['Price', formatPrice(data.price, own)],
    ['Average price', formatPrice(data.average_price, own)],
    ['Invested', data.invested != null ? formatMoney(data.invested, currency) : '–'],
    ['Dividends', data.dividends ? formatMoney(data.dividends, currency) : '–'],
    ['Fees', data.fees ? formatPrice(data.fees, currency) : '–'],
  ]

  return (
    <>
      {back}
      <PageHeader
        title={data.symbol}
        subtitle={[data.name, data.isin, data.first_activity && `held since ${formatDate(data.first_activity)}`]
          .filter(Boolean)
          .join(' · ')}
        actions={
          data.gain_pct != null && (
            <Pill tone={data.gain_pct > 0 ? 'up' : data.gain_pct < 0 ? 'down' : 'muted'}>{formatSignedPct(data.gain_pct)} gain</Pill>
          )
        }
      />

      <Card title="Price" className="pb-0 md:pb-0">
        <p className="-mt-1 mb-3 flex flex-wrap items-baseline gap-x-3 gap-y-1">
          <span className="text-display leading-tight font-semibold tracking-tight md:text-hero">{formatMoney(data.value, currency)}</span>
          {data.gain_abs != null && (
            <span className={cn('text-body font-semibold', gainTone)}>
              {formatSignedMoney(data.gain_abs, currency)}
              {data.gain_pct != null && ` · ${formatSignedPct(data.gain_pct)}`}
            </span>
          )}
        </p>
        <LineChart
          points={data.history.map((p) => ({ d: p.d, a: p.price, b: data.average_price }))}
          aLabel="Price"
          bLabel="Your average now"
          format={(n) => formatPrice(n, own)}
          label={`${data.symbol} price since you first bought it, now ${formatPrice(data.price, own)}; your average price is ${formatPrice(data.average_price, own)}.`}
          bleed
        />
      </Card>

      <Card title="Position" className="mt-5">
        <dl className="grid grid-cols-2 gap-2.5 text-small md:grid-cols-4">
          {figures.map(([label, value, tone]) => (
            <div key={label} className="min-w-0 rounded-[11px] border border-glass-line bg-glass px-3 py-2">
              <dt className="text-micro font-semibold tracking-[0.08em] text-faint uppercase">{label}</dt>
              <dd className={cn('mt-0.5 truncate text-title font-semibold', tone)}>{value}</dd>
            </div>
          ))}
        </dl>
      </Card>

      <Card
        title="Transactions"
        className="mt-5"
        actions={<span className="text-label font-semibold tracking-[0.08em] text-faint uppercase">From Ghostfolio</span>}
      >
        {data.activities.length === 0 ? (
          <p className="text-muted">No transactions recorded.</p>
        ) : (
          <table className="w-full text-small">
            <caption className="sr-only">Transactions in {data.symbol}, newest first</caption>
            <thead>
              <tr className="text-left text-caption text-faint">
                <th scope="col" className="w-5 pb-2">
                  <span className="sr-only">Kind</span>
                </th>
                <th scope="col" className="pb-2 font-medium">Date</th>
                <th scope="col" className="pb-2 font-medium">Type</th>
                <th scope="col" className="pb-2 text-right font-medium">Quantity</th>
                <th scope="col" className="hidden pb-2 text-right font-medium sm:table-cell">Price</th>
                <th scope="col" className="pb-2 text-right font-medium">Amount</th>
              </tr>
            </thead>
            <tbody>
              {data.activities.map((a, i) => (
                <tr key={i} className="border-t border-line-soft">
                  <td className="py-2" aria-hidden="true">
                    <span
                      className="block size-[7px] rounded-full"
                      style={{ backgroundColor: TYPE_COLOURS[a.type] ?? 'var(--color-faint)', boxShadow: `0 0 6px ${TYPE_COLOURS[a.type] ?? 'transparent'}` }}
                    />
                  </td>
                  <td className="py-2 whitespace-nowrap text-muted">{formatDate(a.date)}</td>
                  <td className="py-2">
                    <span
                      className="rounded-[6px] px-1.5 py-px text-micro font-semibold tracking-[0.04em] uppercase"
                      style={{
                        color: TYPE_COLOURS[a.type] ?? 'var(--color-muted)',
                        backgroundColor: `color-mix(in srgb, ${TYPE_COLOURS[a.type] ?? 'var(--color-muted)'} 16%, transparent)`,
                      }}
                    >
                      {TYPES[a.type] ?? a.type}
                    </span>
                  </td>
                  <td className="py-2 text-right">{formatQuantity(a.quantity)}</td>
                  <td className="hidden py-2 text-right whitespace-nowrap sm:table-cell">{formatPrice(a.unit_price, a.currency)}</td>
                  <td className="py-2 text-right whitespace-nowrap">
                    {/* Ghostfolio sometimes lacks the day's exchange rate and reports 0. */}
                    {a.value ? formatMoney(a.value, currency) : formatPrice(a.quantity * a.unit_price, a.currency)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>
    </>
  )
}
