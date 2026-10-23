import { formatPercent } from '../../lib/format'
import { Card } from '../ui/Card'

// Theme colours, accent first; red is left out so no slice reads as a loss.
const COLOURS = [
  'var(--color-accent-line)',
  'var(--color-up)',
  'var(--color-warn)',
  '#5aa9e6',
  'var(--color-muted)',
  'var(--color-faint)',
]

const R = 40
const C = 2 * Math.PI * R
/** A small gap between slices, in the same units as the circumference. */
const GAP = 1.6

/** How the value splits over asset classes and cash: a ring, the largest slice in the middle. */
export function AllocationCard({ allocation }: { allocation: { label: string; pct: number }[] }) {
  if (!allocation.length) return null
  const total = allocation.reduce((s, a) => s + a.pct, 0) || 100
  const largest = allocation.reduce((best, a) => (a.pct > best.pct ? a : best), allocation[0])
  // Where each slice starts on the ring, as a running sum of the ones before it.
  const starts = allocation.map((_, i) => allocation.slice(0, i).reduce((s, a) => s + (a.pct / total) * C, 0))
  return (
    <Card title="Allocation">
      <svg
        role="img"
        aria-label={`Allocation: ${allocation.map((a) => `${a.label} ${formatPercent(a.pct)}`).join(', ')}`}
        viewBox="0 0 100 100"
        className="mx-auto mb-3 block w-[150px]"
      >
        <circle cx="50" cy="50" r={R} fill="none" stroke="rgb(255 255 255 / 0.06)" strokeWidth="10" />
        {allocation.map((slice, i) => {
          const share = (slice.pct / total) * C
          const length = Math.max(0, share - (allocation.length > 1 ? GAP : 0))
          const circle = (
            <circle
              key={slice.label}
              cx="50"
              cy="50"
              r={R}
              fill="none"
              stroke={COLOURS[i % COLOURS.length]}
              strokeWidth="10"
              strokeDasharray={`${length.toFixed(2)} ${C.toFixed(2)}`}
              strokeDashoffset={(-starts[i]).toFixed(2)}
              transform="rotate(-90 50 50)"
              style={{ filter: `drop-shadow(0 0 3px ${COLOURS[i % COLOURS.length]})` }}
            />
          )
          return circle
        })}
        <text x="50" y="50" textAnchor="middle" fontSize="16" fontWeight="600" fill="var(--color-fg)">
          {Math.round(largest.pct)}%
        </text>
        <text x="50" y="62" textAnchor="middle" fontSize="8.5" fill="var(--color-muted)">
          {largest.label}
        </text>
      </svg>
      <ul className="space-y-1.5 text-[13.5px]">
        {allocation.map((slice, i) => (
          <li key={slice.label} className="flex items-center gap-2.5">
            <span
              aria-hidden="true"
              className="size-2.5 rounded-[3px]"
              style={{ background: COLOURS[i % COLOURS.length], boxShadow: `0 0 5px ${COLOURS[i % COLOURS.length]}` }}
            />
            <span className="flex-1">{slice.label}</span>
            <span className="text-muted">{formatPercent(slice.pct)}</span>
          </li>
        ))}
      </ul>
    </Card>
  )
}
