import { cn } from '../../lib/cn'
import { formatMoney, formatSignedMoney, formatSignedPct } from '../../lib/format'
import { dayMove } from '../../lib/portfolio'
import type { PortfolioFull } from '../../lib/portfolioTypes'
import { useApi } from '../../lib/useApi'
import { GlowArea } from '../ui/GlowArea'
import { Pill } from '../ui/Pill'
import { Card } from '../ui/Card'
import { Loading, StaleNote, Unavailable } from '../ui/states'
import { AnimatedNumber } from '../ui/AnimatedNumber'

const tone = (n: number) => (n > 0 ? 'text-up' : n < 0 ? 'text-down' : 'text-muted')
const chip = (n: number) => (n > 0 ? 'bg-up/12 text-up' : n < 0 ? 'bg-down/13 text-down' : 'bg-raised text-muted')

const shortDay = new Intl.DateTimeFormat('en-GB', { day: 'numeric', month: 'short' })
/** "2026-10-11" as a local date, "11 Oct". */
const formatShortDay = (d: string) => {
  const [y, m, day] = d.split('-').map(Number)
  return shortDay.format(new Date(y, m - 1, day))
}

/** The portfolio at a glance: its value, today, and the last 30 days edge to edge. */
export function PortfolioCard() {
  const { data, error } = useApi<PortfolioFull>('/api/portfolio', 300_000)
  const today = data && dayMove(data)
  const history = data?.history ?? []
  const first = history[0]?.v
  const last = history.at(-1)?.v
  const periodPct = first && last != null ? ((last - first) / first) * 100 : null
  const high = history.reduce<{ d: string; v: number } | null>((top, p) => (!top || p.v > top.v ? p : top), null)

  return (
    <Card
      title="Portfolio"
      link={{ to: '/portfolio', label: 'Open' }}
      actions={today && <Pill tone={today.pct > 0 ? 'up' : today.pct < 0 ? 'down' : 'muted'}>{formatSignedPct(today.pct)} today</Pill>}
    >
      {!data && (error ? <Unavailable what="The portfolio" /> : <Loading />)}
      {data && today && (
        <>
          <p className="text-display leading-tight font-semibold tracking-tight">
            <AnimatedNumber value={data.total_value} format={(n) => formatMoney(n, data.currency)} />
          </p>
          <p className="mt-0.5 text-small font-semibold">
            <span className={tone(today.abs)}>{formatSignedMoney(today.abs, data.currency)} today</span>
            {periodPct != null && (
              <span className={tone(periodPct)}> · {formatSignedPct(periodPct)} in 30 days</span>
            )}
          </p>

          <div className="-mx-5 mt-2.5 md:-mx-6">
            <GlowArea
              values={history.map((p) => p.v)}
              label="Portfolio value, last 30 days"
              tone={periodPct != null && periodPct < 0 ? 'down' : 'up'}
              height={110}
            />
          </div>
          <div className="mt-1.5 mb-2 flex flex-wrap justify-between gap-x-3 text-label font-semibold tracking-[0.08em] uppercase">
            <span className="text-faint">Last 30 days</span>
            {high && history.length > 1 && (
              <span className="text-muted">
                High {formatMoney(high.v, data.currency)} · {formatShortDay(high.d)}
              </span>
            )}
          </div>

          <table className="w-full table-fixed text-small">
            <caption className="sr-only">Largest holdings</caption>
            <colgroup>
              <col className="w-[4.5rem]" />
              <col />
              <col className="w-24" />
              <col className="w-[4.75rem]" />
            </colgroup>
            <tbody>
              {data.holdings.slice(0, 3).map((h) => (
                <tr key={h.symbol} className="border-t border-line-soft first:border-t-0">
                  <td className="py-1.5 pr-2">
                    <span className="inline-block min-w-[3.25rem] truncate rounded-[6px] border border-glass-line bg-glass px-1.5 py-0.5 text-center font-mono text-caption">
                      {h.symbol}
                    </span>
                  </td>
                  <td className="truncate py-1.5 pr-3 text-muted" title={h.name}>
                    {h.name}
                  </td>
                  <td className="py-1.5 pr-3 text-right whitespace-nowrap">{formatMoney(h.value, data.currency)}</td>
                  <td className="py-1.5 text-right">
                    <span className={cn('rounded-[7px] px-1.5 py-0.5 text-caption font-semibold whitespace-nowrap', chip(h.day_pct))}>
                      {formatSignedPct(h.day_pct)}
                    </span>
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
