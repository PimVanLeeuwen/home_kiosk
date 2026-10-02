import { ChevronLeft } from 'lucide-react'
import { Link } from 'react-router'
import { cn } from '../../lib/cn'
import { formatDate, formatMoney, formatPrice, formatQuantity, formatSignedMoney, formatSignedPct } from '../../lib/format'
import type { HoldingDetail } from '../../lib/portfolioTypes'
import { useApi } from '../../lib/useApi'
import { PageHeader } from '../PageHeader'
import { Card } from '../home/Card'
import { LineChart } from './LineChart'

const TYPES: Record<string, string> = {
  BUY: 'Buy',
  SELL: 'Sell',
  DIVIDEND: 'Dividend',
  FEE: 'Fee',
  INTEREST: 'Interest',
  LIABILITY: 'Liability',
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
    <Link to="/portfolio" className="mb-4 inline-flex items-center gap-1 text-[13px] text-accent-fg hover:underline">
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
          <p className="text-muted">This holding is not available right now.</p>
        ) : (
          <p role="status" className="text-muted">
            Loading…
          </p>
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
      />
      <div className="grid gap-4 lg:grid-cols-[minmax(0,2fr)_minmax(0,1fr)]">
        <Card title="Price">
          <LineChart
            points={data.history.map((p) => ({ d: p.d, a: p.price, b: data.average_price }))}
            aLabel="Price"
            bLabel="Your average now"
            format={(n) => formatPrice(n, own)}
            label={`${data.symbol} price since you first bought it, now ${formatPrice(data.price, own)}; your average price is ${formatPrice(data.average_price, own)}.`}
          />
        </Card>
        <Card title="Position">
          <dl className="grid grid-cols-2 gap-x-4 gap-y-3 text-[13.5px]">
            {figures.map(([label, value, tone]) => (
              <div key={label}>
                <dt className="text-[12px] text-faint">{label}</dt>
                <dd className={cn('font-medium', tone)}>{value}</dd>
              </div>
            ))}
          </dl>
        </Card>
      </div>

      <Card title="Transactions" className="mt-4">
        {data.activities.length === 0 ? (
          <p className="text-muted">No transactions recorded.</p>
        ) : (
          <table className="w-full text-[13.5px]">
            <caption className="sr-only">Transactions in {data.symbol}, newest first</caption>
            <thead>
              <tr className="text-left text-[12px] text-faint">
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
                  <td className="py-2 whitespace-nowrap">{formatDate(a.date)}</td>
                  <td className="py-2">{TYPES[a.type] ?? a.type}</td>
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
