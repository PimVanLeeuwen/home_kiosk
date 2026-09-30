import { cn } from '../../lib/cn'
import { formatMoney, formatSignedPct } from '../../lib/format'
import type { Portfolio } from '../../lib/types'
import { useApi } from '../../lib/useApi'
import { Card, Loading, StaleNote, Unavailable } from './Card'
import { Sparkline } from './Sparkline'

const tone = (n: number) => (n > 0 ? 'text-up' : n < 0 ? 'text-down' : 'text-muted')

export function PortfolioCard() {
  const { data, error } = useApi<Portfolio>('/api/portfolio', 300_000)

  return (
    <Card title="Portfolio" link={{ to: '/portfolio', label: 'Open' }}>
      {!data && (error ? <Unavailable what="The portfolio" /> : <Loading />)}
      {data && (
        <>
          <p className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
            <span className="text-[30px] font-semibold tracking-tight md:text-[34px]">
              {formatMoney(data.total_value, data.currency)}
            </span>
            <span className={cn('font-semibold', tone(data.change.day_abs))}>
              {formatMoney(data.change.day_abs, data.currency)} · {formatSignedPct(data.change.day_pct)} today
            </span>
          </p>
          <Sparkline values={data.history.map((p) => p.v)} label="Portfolio value, last 30 days" />
          <p className="mb-3 text-[11px] font-semibold tracking-[0.08em] text-faint uppercase">Last 30 days</p>
          <table className="w-full table-fixed text-[13.5px]">
            <caption className="sr-only">Largest holdings</caption>
            <tbody>
              {data.holdings.slice(0, 3).map((h) => (
                <tr key={h.symbol}>
                  <td className="truncate py-1 pr-3" title={`${h.symbol} ${h.name}`}>
                    <span className="font-mono text-[12.5px]">{h.symbol}</span>{' '}
                    <span className="text-muted">{h.name}</span>
                  </td>
                  <td className="w-24 py-1 pr-3 text-right whitespace-nowrap">{formatMoney(h.value, data.currency)}</td>
                  <td className={cn('w-18 py-1 text-right whitespace-nowrap', tone(h.day_pct))}>
                    {formatSignedPct(h.day_pct)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {data.stale && <StaleNote />}
        </>
      )}
    </Card>
  )
}
