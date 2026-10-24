import { useId, useState, type PointerEvent } from 'react'
import { cn } from '../../lib/cn'
import { formatChartDate, formatDate } from '../../lib/format'

export interface LinePoint {
  d: string
  /** The main series, drawn as a filled line. */
  a: number
  /** A reference series, dashed (amount invested, your average price). */
  b?: number | null
}

interface Props {
  points: LinePoint[]
  aLabel: string
  bLabel?: string
  format: (n: number) => string
  /** Spoken summary of the chart. */
  label: string
  /** Run the chart to the card's edges (the readout and dates keep the padding). */
  bleed?: boolean
}

const WIDTH = 800
const HEIGHT = 220

/** A line over time with a readout: the latest point, or the one under the pointer. Green or
 * red by the period's direction, glowing, with the period's high marked. */
export function LineChart({ points, aLabel, bLabel, format, label, bleed }: Props) {
  const gradient = useId()
  const [hover, setHover] = useState<number | null>(null)
  if (points.length < 2) return <p className="py-16 text-center text-small text-faint">Not enough history yet.</p>

  const values = points.flatMap((p) => (p.b != null ? [p.a, p.b] : [p.a]))
  const lo = Math.min(...values)
  const hi = Math.max(...values)
  const pad = (hi - lo || Math.abs(hi) || 1) * 0.06
  const min = lo - pad
  const max = hi + pad
  const x = (i: number) => (i / (points.length - 1)) * WIDTH
  const y = (v: number) => HEIGHT - ((v - min) / (max - min)) * HEIGHT
  const path = (get: (p: LinePoint) => number | null | undefined) =>
    points
      .map((p, i) => [i, get(p)] as const)
      .filter(([, v]) => v != null)
      .map(([i, v], n) => `${n ? 'L' : 'M'}${x(i).toFixed(1)} ${y(v!).toFixed(1)}`)
      .join(' ')
  const line = path((p) => p.a)
  const reference = bLabel ? path((p) => p.b) : ''

  const days = (Date.parse(points.at(-1)!.d) - Date.parse(points[0].d)) / 86_400_000
  const long = days > 300
  const shown = points[hover ?? points.length - 1]
  const rising = points.at(-1)!.a >= points[0].a
  const colour = rising ? 'var(--color-up)' : 'var(--color-down)'
  const top = points.reduce((best, p, i) => (p.a > points[best].a ? i : best), 0)
  const topX = (x(top) / WIDTH) * 100
  const topY = (y(points[top].a) / HEIGHT) * 100

  function onMove(event: PointerEvent<HTMLDivElement>) {
    const rect = event.currentTarget.getBoundingClientRect()
    const ratio = Math.min(1, Math.max(0, (event.clientX - rect.left) / rect.width))
    setHover(Math.round(ratio * (points.length - 1)))
  }

  return (
    <div>
      <p aria-live="off" className="mb-2 flex flex-wrap items-baseline gap-x-4 gap-y-0.5 text-small">
        <span className="text-faint">{formatDate(shown.d)}</span>
        <span>
          <span className="mr-1.5 inline-block size-2 rounded-full align-middle" style={{ backgroundColor: colour, boxShadow: `0 0 6px ${colour}` }} aria-hidden="true" />
          {aLabel} <span className="font-semibold">{format(shown.a)}</span>
        </span>
        {bLabel && shown.b != null && (
          <span className="text-muted">
            <span className="mr-1.5 inline-block w-3 border-t-2 border-dashed border-muted align-middle" aria-hidden="true" />
            {bLabel} <span className="font-medium text-fg">{format(shown.b)}</span>
          </span>
        )}
      </p>
      <div
        data-tone={rising ? 'up' : 'down'}
        className={cn('relative touch-pan-y', bleed && '-mx-5 md:-mx-6')}
        onPointerMove={onMove}
        onPointerDown={onMove}
        onPointerLeave={() => setHover(null)}
      >
        <svg viewBox={`0 0 ${WIDTH} ${HEIGHT}`} preserveAspectRatio="none" role="img" aria-label={label} className="h-[200px] w-full md:h-[240px]">
          <defs>
            <linearGradient id={gradient} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0" stopColor={colour} stopOpacity="0.3" />
              <stop offset="1" stopColor={colour} stopOpacity="0" />
            </linearGradient>
          </defs>
          {[0.25, 0.5, 0.75].map((f) => (
            <line key={f} x1="0" x2={WIDTH} y1={HEIGHT * f} y2={HEIGHT * f} stroke="rgb(255 255 255 / 0.04)" vectorEffect="non-scaling-stroke" />
          ))}
          <path d={`${line} L${WIDTH} ${HEIGHT} L0 ${HEIGHT} Z`} fill={`url(#${gradient})`} />
          {reference && (
            <path d={reference} fill="none" stroke="var(--color-muted)" strokeWidth="1.5" strokeDasharray="5 5" vectorEffect="non-scaling-stroke" />
          )}
          <path
            d={line}
            fill="none"
            stroke={colour}
            strokeWidth="2.2"
            strokeLinejoin="round"
            vectorEffect="non-scaling-stroke"
            style={{ filter: `drop-shadow(0 0 4px ${colour})` }}
          />
        </svg>
        {hover != null && (
          <>
            <div aria-hidden="true" className="pointer-events-none absolute inset-y-0 w-px bg-faint/60" style={{ left: `${(x(hover) / WIDTH) * 100}%` }} />
            <div
              aria-hidden="true"
              className="pointer-events-none absolute size-2.5 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-panel"
              style={{ backgroundColor: colour, left: `${(x(hover) / WIDTH) * 100}%`, top: `${(y(points[hover].a) / HEIGHT) * 100}%` }}
            />
          </>
        )}
        {/* The period's high as a glowing dot; its amount sits in the date row below. */}
        <span
          aria-hidden="true"
          className="pointer-events-none absolute size-2 -translate-x-1/2 -translate-y-1/2 rounded-full"
          style={{ left: `${topX}%`, top: `${topY}%`, backgroundColor: colour, boxShadow: `0 0 8px ${colour}` }}
        />
      </div>
      <div aria-hidden="true" className={cn('mt-1.5 flex justify-between text-label text-faint', bleed && 'pb-4')}>
        <span>{formatChartDate(points[0].d, long)}</span>
        <span className="text-muted">high {format(points[top].a)}</span>
        <span>{formatChartDate(points.at(-1)!.d, long)}</span>
      </div>
    </div>
  )
}
