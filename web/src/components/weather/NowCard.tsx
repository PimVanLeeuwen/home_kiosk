import { formatTime } from '../../lib/format'
import { rainSummary, WET_MM } from '../../lib/rain'
import type { Weather } from '../../lib/types'
import { useApi } from '../../lib/useApi'
import { cn } from '../../lib/cn'
import { Card } from '../ui/Card'
import { Loading, StaleNote, Unavailable } from '../ui/states'
import { SunArc } from './SunArc'

const whole = (n: number) => Math.round(n)

/** A small labelled figure under the temperature: feels like, wind, humidity. */
function Figure({ label, value }: { label: string; value: string }) {
  return (
    <div className="min-w-0">
      <dt className="text-label eyebrow text-faint">{label}</dt>
      <dd className="mt-0.5 truncate text-title">{value}</dd>
    </div>
  )
}

/**
 * The Weather page's Now (plan.md M38, 5b): the temperature large and light, what it is like and
 * the next two hours beside it, three small figures, and the sun's day. Today's Weather card keeps
 * the rain ring.
 */
export function NowCard() {
  const { data: w, error } = useApi<Weather>('/api/weather', 300_000)
  const now = new Date()
  const wet = w?.rain.some((p) => p.mm_per_hour >= WET_MM)
  const figures = w
    ? ([
        w.feel_temperature != null && ['Feels like', `${whole(w.feel_temperature)} °C`],
        w.wind_bft != null && ['Wind', `${w.wind_bft} Bft${w.wind_direction ? ` ${w.wind_direction}` : ''}`],
        w.humidity != null && ['Humidity', `${whole(w.humidity)}%`],
      ].filter(Boolean) as [string, string][])
    : []

  return (
    <Card title="Now" note={w && w.station.replace(/^Meetstation /, '')}>
      {!w && (error ? <Unavailable what="The weather" /> : <Loading />)}
      {w && (
        <>
          <div className="flex flex-wrap items-end gap-x-5 gap-y-2">
            {w.temperature != null && <p className="text-hero leading-none font-medium tracking-[-0.04em]">{whole(w.temperature)}°</p>}
            <div className="min-w-0 pb-1.5">
              {w.description && <p className="text-muted">{w.description}</p>}
              <p className={cn('font-medium', wet && 'text-accent-fg')}>{rainSummary(w.rain)}</p>
            </div>
          </div>

          {figures.length > 0 && (
            <dl className="mt-5 grid grid-cols-3 gap-3 border-t border-line-soft pt-4">
              {figures.map(([label, value]) => (
                <Figure key={label} label={label} value={value} />
              ))}
            </dl>
          )}

          {w.sunrise && w.sunset && (
            <div className="mt-4 border-t border-line-soft pt-4">
              <p className="text-label eyebrow text-faint">
                <span className="whitespace-nowrap">Sunrise {formatTime(w.sunrise)}</span> ·{' '}
                <span className="whitespace-nowrap">Sunset {formatTime(w.sunset)}</span>
              </p>
              <div className="mt-1 max-w-56">
                <SunArc sunrise={w.sunrise} sunset={w.sunset} now={now} />
              </div>
            </div>
          )}

          <p className="mt-3 text-small text-faint">
            Data from{' '}
            <a href="https://www.buienradar.nl" target="_blank" rel="noreferrer" className="hit text-muted hover:underline">
              Buienradar
            </a>
          </p>
          {w.stale && <StaleNote />}
        </>
      )}
    </Card>
  )
}
