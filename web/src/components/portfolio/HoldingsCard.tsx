import { ChevronRight } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router'
import { cn } from '../../lib/cn'
import { formatMoney, formatPercent, formatSignedMoney, formatSignedPct } from '../../lib/format'
import { holdingPath } from '../../lib/portfolio'
import type { HoldingRow } from '../../lib/portfolioTypes'
import { Card } from '../home/Card'
import { FilterPill } from '../news/FilterPill'

type Sort = 'value' | 'today' | 'gain'
const SORTS: [Sort, string][] = [
  ['value', 'Value'],
  ['today', 'Today'],
  ['gain', 'Gain'],
]

const tone = (n: number | null | undefined) => (!n ? 'text-muted' : n > 0 ? 'text-up' : 'text-down')

function sorted(holdings: HoldingRow[], sort: Sort): HoldingRow[] {
  const key = (h: HoldingRow) => (sort === 'value' ? h.value : sort === 'today' ? h.day_pct : (h.gain_pct ?? 0))
  return [...holdings].sort((a, b) => key(b) - key(a))
}

/** Every position, as a table on laptops and a list on phones; each opens its detail. */
export function HoldingsCard({ holdings, currency }: { holdings: HoldingRow[]; currency: string }) {
  const [sort, setSort] = useState<Sort>('value')
  const rows = sorted(holdings, sort)
  const money = (n: number) => formatMoney(n, currency)

  return (
    <Card
      title={`Holdings (${holdings.length})`}
      actions={
        <div role="group" aria-label="Sort by" className="flex gap-1">
          {SORTS.map(([s, label]) => (
            <FilterPill key={s} on={sort === s} onClick={() => setSort(s)}>
              {label}
            </FilterPill>
          ))}
        </div>
      }
    >
      <table className="hidden w-full text-[13.5px] md:table">
        <caption className="sr-only">Holdings, sorted by {sort}</caption>
        <thead>
          <tr className="text-left text-[12px] text-faint">
            <th scope="col" className="w-[40%] pb-2 font-medium">Holding</th>
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
            <tr key={h.symbol} className="group relative border-t border-line-soft hover:bg-raised">
              <td className="max-w-0 py-2.5 pr-3">
                <Link to={holdingPath(h)} className="block after:absolute after:inset-0" title={h.name}>
                  <span className="block font-mono text-[12.5px] font-medium">{h.symbol}</span>
                  <span className="block truncate text-[12.5px] text-muted">{h.name}</span>
                </Link>
              </td>
              <td className="py-2.5 pl-3 text-right whitespace-nowrap">{money(h.value)}</td>
              <td className="py-2.5 pl-3 text-right whitespace-nowrap text-muted">{formatPercent(h.weight_pct)}</td>
              <td className={cn('py-2.5 pl-3 text-right whitespace-nowrap', tone(h.day_pct))}>
                {formatSignedPct(h.day_pct)}
                {h.day_abs != null && <span className="block text-[12px] opacity-80">{formatSignedMoney(h.day_abs, currency)}</span>}
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
              <span className="min-w-0 flex-1">
                <span className="block font-mono text-[13px] font-medium">{h.symbol}</span>
                <span className="block truncate text-[12.5px] text-muted">{h.name}</span>
              </span>
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
