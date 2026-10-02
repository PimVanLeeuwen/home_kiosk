import { formatPercent } from '../../lib/format'
import { Card } from '../home/Card'

// Theme colours, accent first; red is left out so no slice reads as a loss.
const COLOURS = [
  'var(--color-accent-line)',
  'var(--color-up)',
  'var(--color-warn)',
  '#5aa9e6',
  'var(--color-muted)',
  'var(--color-faint)',
]

/** How the value splits over asset classes and cash. */
export function AllocationCard({ allocation }: { allocation: { label: string; pct: number }[] }) {
  if (!allocation.length) return null
  return (
    <Card title="Allocation">
      <div aria-hidden="true" className="mb-4 flex h-3 overflow-hidden rounded-full bg-raised">
        {allocation.map((slice, i) => (
          <span key={slice.label} style={{ width: `${slice.pct}%`, background: COLOURS[i % COLOURS.length] }} />
        ))}
      </div>
      <ul className="space-y-1.5 text-[13.5px]">
        {allocation.map((slice, i) => (
          <li key={slice.label} className="flex items-center gap-2.5">
            <span aria-hidden="true" className="size-2.5 rounded-sm" style={{ background: COLOURS[i % COLOURS.length] }} />
            <span className="flex-1">{slice.label}</span>
            <span className="text-muted">{formatPercent(slice.pct)}</span>
          </li>
        ))}
      </ul>
    </Card>
  )
}
