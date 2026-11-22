import { LEVEL, OPEN_FROM, STUFFY_FROM, type AirLevel } from '../../lib/air'
import type { Air } from '../../lib/types'
import { SvgLabel } from '../ui/SvgLabel'

/** The ring runs over three quarters of a circle, from 400 to 2000 ppm. */
const LOW = 400
const HIGH = 2000
const R = 80
const START = 135 // degrees, clockwise from 3 o'clock
const SPAN = 270

function share(ppm: number) {
  return Math.max(0, Math.min(1, (ppm - LOW) / (HIGH - LOW)))
}

function point(angle: number, r = R) {
  const a = (angle * Math.PI) / 180
  return [100 + r * Math.cos(a), 100 + r * Math.sin(a)] as const
}

function arc(from: number, to: number) {
  const [x0, y0] = point(from)
  const [x1, y1] = point(to)
  return `M ${x0.toFixed(1)} ${y0.toFixed(1)} A ${R} ${R} 0 ${to - from > 180 ? 1 : 0} 1 ${x1.toFixed(1)} ${y1.toFixed(1)}`
}

/** CO2 as a gauge: the track with gaps at 800 and 1200, filled to now in the level's colour. */
export function Co2Ring({ ppm, level }: { ppm: number; level: AirLevel }) {
  const { word, colour } = LEVEL[level]
  const to = START + SPAN * share(ppm)
  const [hx, hy] = point(to)
  return (
    <div className="relative w-full max-w-[200px]">
      <svg viewBox="0 0 200 200" className="block w-full" role="img" aria-label={`CO₂ ${ppm} ppm, ${word.toLowerCase()}`}>
        <path d={arc(START, START + SPAN)} fill="none" stroke="var(--color-track)" strokeWidth="13" strokeLinecap="round" />
        {[STUFFY_FROM, OPEN_FROM].map((t) => {
          const a = START + SPAN * share(t)
          const [x0, y0] = point(a, R - 10)
          const [x1, y1] = point(a, R + 10)
          return <line key={t} x1={x0} y1={y0} x2={x1} y2={y1} stroke="var(--color-card)" strokeWidth="3" />
        })}
        <path
          d={arc(START, Math.max(to, START + 0.5))}
          pathLength={1}
          strokeDasharray="1 1"
          fill="none"
          stroke={colour}
          strokeWidth="13"
          strokeLinecap="round"
          style={{ filter: `drop-shadow(0 0 4px ${colour})` }}
          className="motion-safe:animate-sweep"
        />
        <circle cx={hx} cy={hy} r="8.5" fill="#fff" />
        <text
          x="100"
          y="104"
          textAnchor="middle"
          fill="currentColor"
          fontSize="40"
          fontWeight="600"
          style={{ fontVariantNumeric: 'tabular-nums' }}
        >
          {ppm}
        </text>
      </svg>
      <SvgLabel x={100} y={126} w={200} h={200} className="text-label text-muted">
        ppm CO₂
      </SvgLabel>
    </div>
  )
}

const CURVE_LOW = 350
const CURVE_HIGH = 1600

/** CO2 over the last 8 hours, with dashed lines at 800 and 1200. */
export function Co2Curve({ history, level, tall = false }: { history: Air['history']; level: AirLevel; tall?: boolean }) {
  if (history.length < 2) return null
  const w = 600
  const h = 110
  const x = (i: number) => (i / (history.length - 1)) * w
  const y = (v: number) => h - ((Math.min(Math.max(v, CURVE_LOW), CURVE_HIGH) - CURVE_LOW) / (CURVE_HIGH - CURVE_LOW)) * h
  const line = history.map((p, i) => `${i ? 'L' : 'M'} ${x(i).toFixed(1)} ${y(p.co2).toFixed(1)}`).join(' ')
  const { colour } = LEVEL[level]
  return (
    <figure className="mt-4">
      <svg
        viewBox={`0 0 ${w} ${h}`}
        preserveAspectRatio="none"
        className={`block w-full motion-safe:animate-reveal ${tall ? 'h-40' : 'h-[84px]'}`}
        role="img"
        aria-label="CO₂ over the last 8 hours"
      >
        {[STUFFY_FROM, OPEN_FROM].map((t) => (
          <line
            key={t}
            x1="0"
            x2={w}
            y1={y(t)}
            y2={y(t)}
            stroke="rgb(255 255 255 / 0.1)"
            strokeDasharray="5 7"
            vectorEffect="non-scaling-stroke"
          />
        ))}
        <path d={`${line} L ${w} ${h} L 0 ${h} Z`} fill={colour} fillOpacity="0.13" className="motion-safe:animate-fill-in" />
        <path d={line} fill="none" stroke={colour} strokeWidth="2" strokeLinejoin="round" vectorEffect="non-scaling-stroke" />
      </svg>
      <figcaption className="mt-1 flex justify-between text-label text-faint">
        <span>8 h ago</span>
        <span>now</span>
      </figcaption>
    </figure>
  )
}
