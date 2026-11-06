import { useId, useState, type PointerEvent } from 'react'
import { formatPrice, pointTime, type StockWeek, type WeekView } from '../../lib/stockWeek'

const WIDTH = 800
const HEIGHT = 260
/** Room above the line for the high's label and below it for the low's, in viewBox units. */
const TOP = 34
const BOTTOM = 30

/** Keeps a label's centre (in percent) far enough from the edges for its text. */
const clamp = (percent: number) => Math.min(92, Math.max(8, percent))

/** A point's label: centred on it, but held inside the chart (which runs to the card's edges)
 * near either end, where a centred label would be cut off. */
function edge(percent: number): { left?: string; right?: string; transform?: string } {
  if (percent < 15) return { left: `max(${percent}% - 8px, 12px)` }
  if (percent > 85) return { right: `max(${100 - percent}% - 8px, 12px)` }
  return { left: `${percent}%`, transform: 'translateX(-50%)' }
}

/** One holding's week: the line glowing over a fading fill, a dashed line at the close before
 * the week, the trading days apart, the high and the low marked, a ripple on the latest
 * price, and a readout of the point under the pointer. */
export function WeekChart({ stock, view }: { stock: StockWeek; view: WeekView }) {
  const gradient = useId()
  const [hover, setHover] = useState<number | null>(null)
  const prices = stock.points.map((p) => p.price)
  const lo = Math.min(view.base, ...prices)
  const hi = Math.max(view.base, ...prices)
  const span = hi - lo || 1
  const last = prices.length - 1
  const x = (i: number) => (i / last) * WIDTH * 0.97 // room right of the line for the ripple
  const y = (v: number) => TOP + (1 - (v - lo) / span) * (HEIGHT - TOP - BOTTOM)
  const pct = (px: number, of: number) => `${(px / of) * 100}%`
  const line = prices.map((p, i) => `${i ? 'L' : 'M'}${x(i).toFixed(1)} ${y(p).toFixed(1)}`).join(' ')
  const up = view.change >= 0
  const colour = up ? 'var(--color-up)' : 'var(--color-down)'
  const shown = hover ?? last
  const price = (n: number) => formatPrice(n, stock.currency)

  function onMove(event: PointerEvent<HTMLDivElement>) {
    const rect = event.currentTarget.getBoundingClientRect()
    const ratio = Math.min(1, Math.max(0, (event.clientX - rect.left) / (rect.width * 0.97)))
    setHover(Math.round(ratio * last))
  }

  const mark = (i: number, over: boolean) =>
    i !== last && (
      <span
        aria-hidden="true"
        className="pointer-events-none absolute rounded-[5px] bg-card/75 px-1 text-caption whitespace-nowrap"
        style={{ ...edge((x(i) / WIDTH) * 100), top: `calc(${pct(y(prices[i]), HEIGHT)} ${over ? '- 26px' : '+ 8px'})` }}
      >
        <span className={over ? 'text-fg' : 'text-muted'}>{price(prices[i])}</span>
      </span>
    )
  // Next to the latest price its ripple marks the spot; a second circle would touch it.
  const dot = (i: number) =>
    i < last - 1 && (
      <span
        aria-hidden="true"
        className="pointer-events-none absolute size-2.5 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-fg bg-canvas"
        style={{ left: pct(x(i), WIDTH), top: pct(y(prices[i]), HEIGHT) }}
      />
    )

  return (
    <div>
      <p aria-live="off" className="mb-2 flex flex-wrap items-baseline gap-x-4 gap-y-0.5 text-small">
        <span className="text-faint">{pointTime(stock, shown)}</span>
        <span>
          <span className="mr-1.5 inline-block size-2 rounded-full align-middle" style={{ backgroundColor: colour, boxShadow: `0 0 6px ${colour}` }} aria-hidden="true" />
          <span className="font-semibold">{price(prices[shown])}</span>
        </span>
        <span className="text-muted">
          <span className="mr-1.5 inline-block w-3 border-t-2 border-dashed border-muted align-middle" aria-hidden="true" />
          Previous close <span className="font-medium text-fg">{price(view.base)}</span>
        </span>
      </p>
      <div
        data-tone={up ? 'up' : 'down'}
        className="relative -mx-5 touch-pan-y md:-mx-6"
        onPointerMove={onMove}
        onPointerDown={onMove}
        onPointerLeave={() => setHover(null)}
      >
        <svg
          viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
          preserveAspectRatio="none"
          role="img"
          aria-label={`${stock.symbol} over its last five trading days`}
          className="h-[230px] w-full motion-safe:animate-reveal md:h-[270px]"
        >
          <defs>
            <linearGradient id={gradient} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0" stopColor={colour} stopOpacity="0.32" />
              <stop offset="1" stopColor={colour} stopOpacity="0" />
            </linearGradient>
          </defs>
          {view.days.slice(1).map((d) => (
            <line key={d.at} x1={x(d.at)} x2={x(d.at)} y1="0" y2={HEIGHT} stroke="rgb(255 255 255 / 0.07)" vectorEffect="non-scaling-stroke" />
          ))}
          <path d={`${line} L${x(last)} ${HEIGHT} L0 ${HEIGHT} Z`} fill={`url(#${gradient})`} className="motion-safe:animate-fill-in" />
          <line
            x1="0"
            x2={WIDTH}
            y1={y(view.base)}
            y2={y(view.base)}
            stroke="var(--color-muted)"
            strokeWidth="1.5"
            strokeDasharray="5 5"
            vectorEffect="non-scaling-stroke"
          />
          <path
            d={line}
            fill="none"
            stroke={colour}
            strokeWidth="2.4"
            strokeLinejoin="round"
            vectorEffect="non-scaling-stroke"
            style={{ filter: `drop-shadow(0 0 5px ${colour})` }}
          />
        </svg>
        {dot(view.high)}
        {dot(view.low)}
        {mark(view.high, true)}
        {mark(view.low, false)}
        {/* The latest price, with a ripple going out from it. */}
        <span
          aria-hidden="true"
          className="pointer-events-none absolute size-6 -translate-x-1/2 -translate-y-1/2"
          style={{ left: pct(x(last), WIDTH), top: pct(y(prices[last]), HEIGHT) }}
        >
          <span className="absolute inset-0 rounded-full border-2 motion-safe:animate-ripple" style={{ borderColor: colour }} />
          <span className="absolute inset-[7px] rounded-full border-2 border-fg" style={{ backgroundColor: colour }} />
        </span>
        {hover != null && (
          <>
            <div aria-hidden="true" className="pointer-events-none absolute inset-y-0 w-px bg-faint/60" style={{ left: pct(x(hover), WIDTH) }} />
            <div
              aria-hidden="true"
              className="pointer-events-none absolute size-2.5 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-panel"
              style={{ backgroundColor: colour, left: pct(x(hover), WIDTH), top: pct(y(prices[hover]), HEIGHT) }}
            />
          </>
        )}
      </div>
      {/* Each day's name under the middle of its stretch of the line. */}
      <div aria-hidden="true" className="relative mt-1.5 h-4 text-label text-faint">
        {view.days.map((d, n) => {
          const end = n + 1 < view.days.length ? view.days[n + 1].at : last
          return (
            <span key={d.at} className="absolute -translate-x-1/2" style={{ left: `${clamp(((x(d.at) + x(end)) / 2 / WIDTH) * 100)}%` }}>
              {d.label}
            </span>
          )
        })}
      </div>
    </div>
  )
}
