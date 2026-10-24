import { formatTime } from '../../lib/format'
import { rainSummary } from '../../lib/rain'
import type { Weather } from '../../lib/types'
import { useApi } from '../../lib/useApi'
import { RainRing } from '../weather/RainRing'
import { SunArc } from '../weather/SunArc'
import { Card } from '../ui/Card'
import { Loading, StaleNote, Unavailable } from '../ui/states'

const whole = (n: number) => Math.round(n)

/** Outside right now: the temperature inside a ring of the next two hours of rain, and the sun's day. */
export function WeatherCard() {
  const { data: w, error } = useApi<Weather>('/api/weather', 300_000)
  const now = new Date()

  return (
    <Card title="Weather">
      {!w && (error ? <Unavailable what="The weather" /> : <Loading />)}
      {w && (
        <>
          <div className="grid grid-cols-[130px_minmax(0,1fr)] items-center gap-4 sm:grid-cols-[160px_minmax(0,1fr)] sm:gap-5">
            <RainRing points={w.rain} temperature={w.temperature} />
            <div className="min-w-0">
              {w.description && <p className="text-small text-muted">{w.description}</p>}
              <p className="mt-1 text-small font-medium">{rainSummary(w.rain)}</p>
              <p className="mt-2 text-caption text-muted">
                {[
                  w.feel_temperature != null && `Feels like ${whole(w.feel_temperature)} °C`,
                  w.wind_bft != null && `Wind ${w.wind_bft} Bft${w.wind_direction ? ` ${w.wind_direction}` : ''}`,
                  w.humidity != null && `Humidity ${whole(w.humidity)}%`,
                ]
                  .filter(Boolean)
                  .join(' · ')}
              </p>
              {w.sunrise && w.sunset && (
                <div className="mt-3.5">
                  <p className="text-micro font-semibold tracking-[0.08em] text-faint uppercase">
                    <span className="whitespace-nowrap">Sunrise {formatTime(w.sunrise)}</span> ·{' '}
                    <span className="whitespace-nowrap">Sunset {formatTime(w.sunset)}</span>
                  </p>
                  <div className="mt-1">
                    <SunArc sunrise={w.sunrise} sunset={w.sunset} now={now} />
                  </div>
                </div>
              )}
            </div>
          </div>
          <p className="mt-3 text-caption text-faint">
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
