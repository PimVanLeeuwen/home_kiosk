import { formatTime } from '../../lib/format'
import { rainSummary, WET_MM } from '../../lib/rain'
import type { Weather } from '../../lib/types'
import { useApi } from '../../lib/useApi'
import { Card, Loading, StaleNote, Unavailable } from './Card'

const whole = (n: number) => Math.round(n)

/** Rain bars for the next two hours; a light shower still shows, heavy rain tops out. */
function RainBars({ weather }: { weather: Weather }) {
  const points = weather.rain
  if (points.length === 0) return null
  const top = Math.max(2, ...points.map((p) => p.mm_per_hour))
  const width = 100 / points.length
  return (
    <div className="mt-4">
      <svg role="img" aria-label={rainSummary(points)} viewBox="0 0 100 32" preserveAspectRatio="none" className="h-16 w-full">
        <line x1="0" x2="100" y1="31.5" y2="31.5" className="stroke-line-soft" strokeWidth="1" vectorEffect="non-scaling-stroke" />
        {points.map((p, i) => {
          const h = p.mm_per_hour < WET_MM ? 0 : Math.max(2, (Math.sqrt(p.mm_per_hour) / Math.sqrt(top)) * 31)
          return <rect key={p.at} x={i * width + width * 0.15} width={width * 0.7} y={31 - h} height={h} className="fill-accent-line" />
        })}
      </svg>
      <div className="mt-1 flex justify-between text-[11.5px] text-faint">
        <span>{formatTime(points[0].at)}</span>
        <span>{formatTime(points[Math.floor(points.length / 2)].at)}</span>
        <span>{formatTime(points[points.length - 1].at)}</span>
      </div>
    </div>
  )
}

/** Outside right now and rain in the next two hours, from Buienradar. */
export function WeatherCard() {
  const { data: w, error } = useApi<Weather>('/api/weather', 300_000)

  return (
    <Card title="Weather">
      {!w && (error ? <Unavailable what="The weather" /> : <Loading />)}
      {w && (
        <>
          <div className="flex items-baseline gap-3">
            {w.temperature != null && <span className="text-[30px] font-semibold tabular-nums">{whole(w.temperature)} °C</span>}
            {w.description && <span className="text-muted">{w.description}</span>}
          </div>
          <p className="mt-1 text-[12.5px] text-muted">
            {[
              w.feel_temperature != null && `Feels like ${whole(w.feel_temperature)} °C`,
              w.wind_bft != null && `Wind ${w.wind_bft} Bft${w.wind_direction ? ` ${w.wind_direction}` : ''}`,
              w.humidity != null && `Humidity ${whole(w.humidity)}%`,
            ]
              .filter(Boolean)
              .join(' · ')}
          </p>
          <p className="mt-4 text-[13.5px] font-medium">{rainSummary(w.rain)}</p>
          <RainBars weather={w} />
          <p className="mt-3 text-[12px] text-faint">
            {w.sunset && <>Sunset {formatTime(w.sunset)} · </>}
            Data from{' '}
            <a href="https://www.buienradar.nl" target="_blank" rel="noreferrer" className="text-muted hover:underline">
              Buienradar
            </a>
            , {w.station.replace(/^Meetstation /, '')}
          </p>
          {w.stale && <StaleNote />}
        </>
      )}
    </Card>
  )
}
