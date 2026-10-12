import { ChevronRight } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router'
import { cn } from '../../lib/cn'
import { formatMoney, formatPercent, formatSignedMoney, formatSignedPct } from '../../lib/format'
import { holdingPath } from '../../lib/portfolio'
import type { HoldingRow } from '../../lib/portfolioTypes'
import { Card } from '../home/Card'
import { Segmented } from '../ui/Segmented'

type Sort = 'value' | 'today' | 'gain'
const SORTS: [Sort, string][] = [
  ['value', 'Value'],
  ['today', 'Today'],
  ['gain', 'Gain'],
]

const tone = (n: number | null | undefined) => (!n ? 'text-muted' : n > 0 ? 'text-up' : 'text-down')
const pill = (n: number) => (n > 0 ? 'bg-up/12 text-up' : n < 0 ? 'bg-down/13 text-down' : 'bg-raised text-muted')
/** A ticker on a small glass chip. */
const CHIP =
  'inline-block min-w-[3.4rem] shrink-0 rounded-[6px] border border-glass-line bg-glass px-1.5 py-0.5 text-center font-mono text-[12px] font-medium'

function sorted(holdings: HoldingRow[], sort: Sort): HoldingRow[] {
  const key = (h: HoldingRow) => (sort === 'value' ? h.value : sort === 'today' ? h.day_pct : (h.gain_pct ?? 0))
  return [...holdings].sort((a, b) => key(b) - key(a))
}

/** Every position, as a table on laptops and a list on phones; each opens its detail. */
export function HoldingsCard({ holdings, currency }: { holdings: HoldingRow[]; currency: string }) {
  const [sort, setSort] = useState<Sort>('value')
  const rows = sorted(holdings, sort)
  const topWeight = Math.max(1, ...holdings.map((h) => h.weight_pct))
  const money = (n: number) => formatMoney(n, currency)

  return (
    <Card
      title={`Holdings (${holdings.length})`}
      actions={<Segmented label="Sort by" options={SORTS} value={sort} onChange={setSort} />}
    >
      {/* The phone's heat map sends its "others" tile here. */}
      <span id="holdings" className="block scroll-mt-4" />
      <table className="hidden w-full text-[13.5px] md:table">
        <caption className="sr-only">Holdings, sorted by {sort}</caption>
        <thead>
          <tr className="text-left text-[12px] text-faint">
            <th scope="col" className="w-[38%] pb-2 font-medium">Holding</th>
            <th scope="col" className="pb-2 text-right font-medium">Value</th>
            <th scope="col" className="pb-2 text-right font-medium">Weight</th>
            <th scope="col" className="pb-2 text-right font-medium">Today</th>
            <th scope="col" className="pb-2 text-right font-medium">Gain</th>
            <th scope="col" className="w-6 pb-2">
              <span className="sr-only">Open</span>
            </th>
          </tr>
        </thead>
        <tbody>
          {rows.map((h) => (
            <tr key={h.symbol} className="group relative border-t border-line-soft hover:bg-white/[0.03]">
              <td className="max-w-0 py-2.5 pr-3">
                <Link to={holdingPath(h)} className="flex min-w-0 items-center gap-2.5 after:absolute after:inset-0" title={h.name}>
                  <span className={CHIP}>{h.symbol}</span>
                  <span className="truncate text-[12.5px] text-muted">{h.name}</span>
                </Link>
              </td>
              <td className="py-2.5 pl-3 text-right whitespace-nowrap">{money(h.value)}</td>
              <td className="py-2.5 pl-3 text-right whitespace-nowrap text-muted">
                {formatPercent(h.weight_pct)}
                <span className="ml-2 inline-block h-1 w-14 overflow-hidden rounded-full bg-raised align-middle" aria-hidden="true">
                  <span
                    className="block h-full rounded-full bg-linear-to-r from-[#6f60ea] to-[#b4a9ff]"
                    style={{ width: `${Math.min(100, (h.weight_pct / topWeight) * 100)}%` }}
                  />
                </span>
              </td>
              <td className="py-2.5 pl-3 text-right whitespace-nowrap">
                <span className={cn('rounded-[7px] px-1.5 py-0.5 text-[12.5px] font-semibold', pill(h.day_pct))}>{formatSignedPct(h.day_pct)}</span>
                {h.day_abs != null && <span className="mt-0.5 block text-[12px] text-muted">{formatSignedMoney(h.day_abs, currency)}</span>}
              </td>
              <td className={cn('py-2.5 pl-3 text-right whitespace-nowrap', tone(h.gain_pct))}>
                {h.gain_pct != null ? formatSignedPct(h.gain_pct) : '–'}
                {h.gain_abs != null && <span className="block text-[12px] opacity-80">{formatSignedMoney(h.gain_abs, currency)}</span>}
              </td>
              <td className="py-2.5 pl-2 text-faint group-hover:text-fg">
                <ChevronRight aria-hidden="true" className="size-4" />
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      <ul className="md:hidden">
        {rows.map((h) => (
          <li key={h.symbol} className="border-t border-line-soft first:border-t-0">
            <Link to={holdingPath(h)} className="flex items-center gap-3 py-3">
              <span className={CHIP}>{h.symbol}</span>
              <span className="min-w-0 flex-1 truncate text-[12.5px] text-muted">{h.name}</span>
              <span className="text-right whitespace-nowrap">
                <span className="block">{money(h.value)}</span>
                <span className={cn('block text-[12.5px]', tone(sort === 'gain' ? h.gain_pct : h.day_pct))}>
                  {sort === 'gain'
                    ? `${h.gain_pct != null ? formatSignedPct(h.gain_pct) : '–'} total`
                    : `${formatSignedPct(h.day_pct)} today`}
                </span>
              </span>
              <ChevronRight aria-hidden="true" className="size-4 text-faint" />
            </Link>
          </li>
        ))}
      </ul>
    </Card>
  )
}
