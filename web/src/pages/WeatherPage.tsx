import { useState } from 'react'
import { PageHeader } from '../components/PageHeader'
import { Card } from '../components/ui/Card'
import { Pill } from '../components/ui/Pill'
import { Loading, StaleNote, Unavailable } from '../components/ui/states'
import { DayCurve } from '../components/weather/DayCurve'
import { NowCard } from '../components/weather/NowCard'
import { WeekRanges } from '../components/weather/WeekRanges'
import { formatTime } from '../lib/format'
import { useApi } from '../lib/useApi'
import { stampTime, type Forecast, type Radar } from '../lib/weatherTypes'

const localDate = (d: Date) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`

/** Now, today by the hour, the week and, while rain is coming, the radar (plan.md M27, Q). */
export function WeatherPage() {
  const forecast = useApi<Forecast>('/api/forecast', 600_000)
  const radar = useApi<Radar>('/api/radar', 300_000)
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
        <NowCard />
        <Card title={day && day.date !== today ? 'The first day of the forecast' : 'Today'} actions={
            <a href="https://open-meteo.com" target="_blank" rel="noreferrer" className="hit text-small text-muted hover:underline">
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
        {/* While dry the radar is one quiet line, as tall as it needs: the hub reads it only while rain is coming. */}
        <Card
          title="Rain radar"
          note={wet && <>Buienradar · {formatTime(stampTime(radar.data!.stamp!).toISOString())}</>}
          className={wet ? undefined : 'self-start'}
        >
          {wet ? (
            <img
              src={`/api/radar/map?at=${radar.data!.stamp}`}
              onError={() => setFailedFrame(radar.data!.stamp)}
              alt={`The rain radar round home at ${formatTime(stampTime(radar.data!.stamp!).toISOString())}`}
              className="block aspect-[16/10] w-full rounded-tile bg-[#07080f] object-cover"
            />
          ) : (
            <p className="text-small text-muted">
              {(radar.error && !radar.data) || radar.data?.wet
                ? 'The radar is not available right now.'
                : 'Dry for the next 2 hours: the radar shows here when rain is on its way.'}
            </p>
          )}
        </Card>
      </div>
    </>
  )
}
