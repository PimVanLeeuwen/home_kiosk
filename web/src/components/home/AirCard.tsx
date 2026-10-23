import { formatAgo } from '../../lib/format'
import type { Air } from '../../lib/types'
import { useApi } from '../../lib/useApi'
import { Card } from '../ui/Card'
import { Loading, StaleNote, Unavailable } from '../ui/states'

type Level = NonNullable<Air['level']>

/** Plan.md M17: the CO2 words and their colours. */
const LEVEL: Record<Level, { word: string; colour: string; className: string }> = {
  fresh: { word: 'Fresh', colour: 'var(--color-up)', className: 'text-up' },
  stuffy: { word: 'Getting stuffy', colour: 'var(--color-warn)', className: 'text-warn' },
  open_window: { word: 'Open a window', colour: 'var(--color-down)', className: 'text-down' },
}

/** The ring runs over three quarters of a circle, from 400 to 2000 ppm. */
const LOW = 400
const HIGH = 2000
const STUFFY_FROM = 800
const OPEN_FROM = 1200
const R = 80
const START = 135 // degrees, clockwise from 3 o'clock
const SPAN = 270

const degrees = (temperature: number) =>
  new Intl.NumberFormat('nl-NL', { minimumFractionDigits: 1, maximumFractionDigits: 1 }).format(temperature)

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
function Co2Ring({ ppm, level }: { ppm: number; level: Level }) {
  const { word, colour } = LEVEL[level]
  const to = START + SPAN * share(ppm)
  const [hx, hy] = point(to)
  return (
    <svg viewBox="0 0 200 200" className="block w-full max-w-[200px]" role="img" aria-label={`CO₂ ${ppm} ppm, ${word.toLowerCase()}`}>
      <path d={arc(START, START + SPAN)} fill="none" stroke="rgb(255 255 255 / 0.08)" strokeWidth="13" strokeLinecap="round" />
      {[STUFFY_FROM, OPEN_FROM].map((t) => {
        const a = START + SPAN * share(t)
        const [x0, y0] = point(a, R - 10)
        const [x1, y1] = point(a, R + 10)
        return <line key={t} x1={x0} y1={y0} x2={x1} y2={y1} stroke="var(--color-card)" strokeWidth="3" />
      })}
      <path d={arc(START, Math.max(to, START + 0.5))} fill="none" stroke={colour} strokeWidth="13" strokeLinecap="round" style={{ filter: `drop-shadow(0 0 4px ${colour})` }} />
      <circle cx={hx} cy={hy} r="8.5" fill="#fff" />
      <text x="100" y="104" textAnchor="middle" fill="currentColor" fontSize="40" fontWeight="600" style={{ fontVariantNumeric: 'tabular-nums' }}>
        {ppm}
      </text>
      <text x="100" y="128" textAnchor="middle" fill="var(--color-muted)" fontSize="14">
        ppm CO₂
      </text>
    </svg>
  )
}

const CURVE_LOW = 350
const CURVE_HIGH = 1600

/** CO2 over the last 8 hours, with dashed lines at 800 and 1200. */
function Co2Curve({ history, level }: { history: Air['history']; level: Level }) {
  if (history.length < 2) return null
  const w = 600
  const h = 110
  const x = (i: number) => (i / (history.length - 1)) * w
  const y = (v: number) => h - ((Math.min(Math.max(v, CURVE_LOW), CURVE_HIGH) - CURVE_LOW) / (CURVE_HIGH - CURVE_LOW)) * h
  const line = history.map((p, i) => `${i ? 'L' : 'M'} ${x(i).toFixed(1)} ${y(p.co2).toFixed(1)}`).join(' ')
  const { colour } = LEVEL[level]
  return (
    <figure className="mt-4">
      <svg viewBox={`0 0 ${w} ${h}`} preserveAspectRatio="none" className="block h-[84px] w-full" role="img" aria-label="CO₂ over the last 8 hours">
        {[STUFFY_FROM, OPEN_FROM].map((t) => (
          <line key={t} x1="0" x2={w} y1={y(t)} y2={y(t)} stroke="rgb(255 255 255 / 0.1)" strokeDasharray="5 7" vectorEffect="non-scaling-stroke" />
        ))}
        <path d={`${line} L ${w} ${h} L 0 ${h} Z`} fill={colour} fillOpacity="0.13" />
        <path d={line} fill="none" stroke={colour} strokeWidth="2" strokeLinejoin="round" vectorEffect="non-scaling-stroke" />
      </svg>
      <figcaption className="mt-1 flex justify-between text-[11.5px] text-faint">
        <span>8 h ago</span>
        <span>now</span>
      </figcaption>
    </figure>
  )
}

/** The living room's air on Home, the Home panel's Air card (plan.md M17). */
export function AirCard() {
  const { data: air, error } = useApi<Air>('/api/air', 60_000)
  const now = new Date()
  const outside = air?.outside != null ? ` · outside ${air.outside}°` : ''

  return (
    <Card title="Air" actions={air && <span className="text-[12.5px] text-muted">{air.room}{outside}</span>}>
      {!air && (error ? <Unavailable what="The air sensor" /> : <Loading />)}
      {air && (
        <>
          <div className="grid grid-cols-[minmax(0,1fr)_130px] items-center gap-4 sm:grid-cols-[minmax(0,1fr)_170px]">
            <div className="min-w-0">
              <p className="text-[46px] leading-none font-semibold tracking-tight tabular-nums sm:text-[56px]">
                {air.temperature != null ? `${degrees(air.temperature)}°` : '–'}
              </p>
              <ul className="mt-3 grid gap-1 text-[13.5px] text-muted">
                {air.humidity != null && (
                  <li>
                    <span className="font-semibold text-fg">{air.humidity}%</span> humidity
                  </li>
                )}
                {air.pm25 != null && (
                  <li>
                    <span className="font-semibold text-fg">{air.pm25}</span> µg/m³ fine dust
                    {air.quality && <span className="block text-[12px] text-faint">Sensor says: {air.quality}</span>}
                  </li>
                )}
              </ul>
            </div>
            {air.co2 != null && air.level && (
              <div className="grid justify-items-center">
                <Co2Ring ppm={air.co2} level={air.level} />
                <p className={`-mt-3 text-[14px] font-semibold ${LEVEL[air.level].className}`}>{LEVEL[air.level].word}</p>
              </div>
            )}
          </div>
          {air.level && <Co2Curve history={air.history} level={air.level} />}
          {!air.available && <p className="mt-3 text-[12px] text-warn">The sensor is not answering: showing its last values.</p>}
          <p className="mt-3 text-[12px] text-faint">Updated {formatAgo(air.as_of, now)} · IKEA ALPSTUGA</p>
          {air.stale && <StaleNote />}
        </>
      )}
    </Card>
  )
}
