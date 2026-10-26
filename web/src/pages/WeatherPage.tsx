import { useState } from 'react'
import { WeatherCard } from '../components/home/WeatherCard'
import { PageHeader } from '../components/PageHeader'
import { Card } from '../components/ui/Card'
import { Pill } from '../components/ui/Pill'
import { Loading, StaleNote, Unavailable } from '../components/ui/states'
import { DayCurve } from '../components/weather/DayCurve'
import { WeekRanges } from '../components/weather/WeekRanges'
import { formatTime } from '../lib/format'
import type { Weather } from '../lib/types'
import { useApi } from '../lib/useApi'
import { stampTime, type Forecast, type Radar } from '../lib/weatherTypes'

const localDate = (d: Date) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`

/** Now, today by the hour, the week and, while rain is coming, the radar (plan.md M27, Q). */
export function WeatherPage() {
  const forecast = useApi<Forecast>('/api/forecast', 600_000)
  const radar = useApi<Radar>('/api/radar', 300_000)
  const now = useApi<Weather>('/api/weather', 300_000)
  const today = localDate(new Date())
  const day = forecast.data?.days.find((d) => d.date === today) ?? forecast.data?.days[0]
  const [failedFrame, setFailedFrame] = useState<string | null>(null)
  // The picture can be missing for a moment (the first frame not fetched yet): words then.
  const wet = radar.data?.wet && radar.data.stamp && failedFrame !== radar.data.stamp

  return (
    <>
      <PageHeader
        title="Weather"
        subtitle="Now, today and the next 7 days"
        status={radar.data && <Pill tone={radar.data.wet ? 'accent' : 'muted'}>{radar.data.wet ? 'Rain on the way' : 'Dry for now'}</Pill>}
      />
      <div className="grid gap-3.5 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.5fr)] lg:gap-5">
        <WeatherCard onPage />
        <Card title={day && day.date !== today ? 'The first day of the forecast' : 'Today'} actions={
            <a href="https://open-meteo.com" target="_blank" rel="noreferrer" className="text-caption text-muted hover:underline">
              Open-Meteo
            </a>
          }
        >
          {!forecast.data && (forecast.error ? <Unavailable what="The forecast" /> : <Loading />)}
          {day && <DayCurve day={day} now={day.date === today ? new Date() : null} />}
          {forecast.data?.stale && <StaleNote />}
        </Card>
        <Card title="The week">
          {!forecast.data && (forecast.error ? <Unavailable what="The forecast" /> : <Loading />)}
          {forecast.data && <WeekRanges days={forecast.data.days} today={today} />}
        </Card>
        <Card title="Rain radar" actions={wet && <span className="text-caption text-muted">Buienradar · {formatTime(stampTime(radar.data!.stamp!).toISOString())}</span>}>
          {wet ? (
            <img
              src={`/api/radar/map?at=${radar.data!.stamp}`}
              onError={() => setFailedFrame(radar.data!.stamp)}
              alt={`The rain radar round home at ${formatTime(stampTime(radar.data!.stamp!).toISOString())}`}
              className="block aspect-[16/10] w-full rounded-[12px] bg-[#07080f] object-cover"
            />
          ) : (
            <p className="text-small text-muted">
              {(radar.error && !radar.data) || radar.data?.wet
                ? 'The radar is not available right now.'
                : 'No rain expected in the next two hours: the radar shows here when rain is on its way.'}
            </p>
          )}
          {now.data && !wet && <p className="mt-2 text-caption text-faint">The hub reads Buienradar's radar only while rain is coming, every 5 minutes.</p>}
        </Card>
      </div>
    </>
  )
}
