import { useId } from 'react'
import { daySummary, hoursOf, type ForecastDay } from '../../lib/weatherTypes'

const W = 600
const CURVE_TOP = 26
const CURVE_BOTTOM = 118
const RAIN_TOP = 132
const RAIN_BOTTOM = 170

const whole = (n: number) => Math.round(n)
const hh = (hour: number) => `${String(hour).padStart(2, '0')}:00`

/** A smooth line through the points (Catmull-Rom as cubic Béziers). */
function smooth(points: [number, number][]): string {
  return points
    .map(([x, y], i) => {
      if (i === 0) return `M${x.toFixed(1)} ${y.toFixed(1)}`
      const [x0, y0] = points[Math.max(0, i - 2)]
      const [x1, y1] = points[i - 1]
      const [x3, y3] = points[Math.min(points.length - 1, i + 1)]
      const c1 = [x1 + (x - x0) / 6, y1 + (y - y0) / 6]
      const c2 = [x - (x3 - x1) / 6, y - (y3 - y1) / 6]
      return `C${c1[0].toFixed(1)} ${c1[1].toFixed(1)} ${c2[0].toFixed(1)} ${c2[1].toFixed(1)} ${x.toFixed(1)} ${y.toFixed(1)}`
    })
    .join(' ')
}

interface Props {
  day: ForecastDay
  /** Now, when the day is today: a line and a point on the curve. */
  now?: Date | null
}

/**
 * Today on the Weather page (plan.md M27, Q): the temperature by the hour as a
 * warm line, the night shaded either side, the chance of rain as bars below,
 * and a line for now.
 */
export function DayCurve({ day, now = null }: Props) {
  const id = useId()
  const hours = day.hours
  if (hours.length < 2) return null
  const temps = hours.map((h) => h.temperature)
  const lo = Math.min(...temps) - 1
  const hi = Math.max(...temps) + 1
  const x = (hour: number) => (hour / 23) * W
  const y = (t: number) => CURVE_BOTTOM - ((t - lo) / (hi - lo)) * (CURVE_BOTTOM - CURVE_TOP)
  const points = hours.map((h): [number, number] => [x(h.hour), y(h.temperature)])
  const line = smooth(points)
  const warmest = hours.reduce((a, b) => (b.temperature > a.temperature ? b : a))
  const coldest = hours.reduce((a, b) => (b.temperature < a.temperature ? b : a))
  const rise = day.sunrise ? x(Math.min(23, hoursOf(day.sunrise))) : null
  const set = day.sunset ? x(Math.min(23, hoursOf(day.sunset))) : null
  const nowHour = now ? now.getHours() + now.getMinutes() / 60 : null
  const nowTemp =
    nowHour != null
      ? (() => {
          const before = hours.filter((h) => h.hour <= nowHour).at(-1) ?? hours[0]
          const after = hours.find((h) => h.hour > nowHour) ?? before
          const f = after.hour === before.hour ? 0 : (nowHour - before.hour) / (after.hour - before.hour)
          return before.temperature + f * (after.temperature - before.temperature)
        })()
      : null
  const bar = W / 24

  return (
    <figure className="m-0">
      <svg viewBox={`0 0 ${W} ${RAIN_BOTTOM + 22}`} role="img" aria-label={daySummary(day)} className="block w-full overflow-visible">
        <defs>
          <linearGradient id={`${id}fill`} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0" stopColor="#f2a65a" stopOpacity="0.32" />
            <stop offset="1" stopColor="#f2a65a" stopOpacity="0" />
          </linearGradient>
          <linearGradient id={`${id}line`} x1="0" y1="0" x2="1" y2="0">
            <stop offset="0" stopColor="#7cc4ff" />
            <stop offset="0.5" stopColor="#f2a65a" />
            <stop offset="1" stopColor="#c3b9ff" />
          </linearGradient>
        </defs>
        {/* The night either side of the day. */}
        {rise != null && <rect data-night x="0" y="0" width={rise} height={CURVE_BOTTOM + 4} fill="#0c0c18" />}
        {set != null && <rect data-night x={set} y="0" width={W - set} height={CURVE_BOTTOM + 4} fill="#0c0c18" />}
        <path d={`${line} L${W} ${CURVE_BOTTOM} L0 ${CURVE_BOTTOM} Z`} fill={`url(#${id}fill)`} />
        <path d={line} fill="none" stroke={`url(#${id}line)`} strokeWidth="2.5" strokeLinecap="round" />
        <text x={x(warmest.hour)} y={y(warmest.temperature) - 9} textAnchor="middle" fontSize="13" fontWeight="600" fill="#f1eff7">
          {whole(warmest.temperature)}°
        </text>
        <text x={Math.max(14, Math.min(W - 14, x(coldest.hour)))} y={y(coldest.temperature) + 18} textAnchor="middle" fontSize="12" fill="#9a9ea7">
          {whole(coldest.temperature)}°
        </text>

        {/* The chance of rain by the hour. */}
        {hours.map((h) =>
          h.rain_chance > 0 ? (
            <rect
              key={h.hour}
              data-rain={h.rain_chance}
              x={h.hour * bar + 2}
              y={RAIN_BOTTOM - (h.rain_chance / 100) * (RAIN_BOTTOM - RAIN_TOP)}
              width={bar - 4}
              height={(h.rain_chance / 100) * (RAIN_BOTTOM - RAIN_TOP)}
              rx="2"
              fill="#6aa8f0"
              opacity={0.35 + (h.rain_chance / 100) * 0.65}
            />
          ) : null,
        )}
        <line x1="0" x2={W} y1={RAIN_BOTTOM + 0.5} y2={RAIN_BOTTOM + 0.5} stroke="rgb(255 255 255 / 0.08)" />
        {[0, 6, 12, 18, 23].map((h) => (
          <text key={h} x={x(h)} y={RAIN_BOTTOM + 17} textAnchor={h === 0 ? 'start' : h === 23 ? 'end' : 'middle'} fontSize="11" fill="#7e828b">
            {hh(h)}
          </text>
        ))}

        {nowHour != null && nowTemp != null && (
          <g data-now>
            <line x1={x(nowHour)} x2={x(nowHour)} y1="0" y2={RAIN_BOTTOM} stroke="#fff" strokeOpacity="0.7" strokeWidth="1.5" />
            <circle cx={x(nowHour)} cy={y(nowTemp)} r="5" fill="#fff" />
          </g>
        )}
      </svg>
    </figure>
  )
}
