import { Co2Curve, Co2Ring } from '../components/air/Co2'
import { PageHeader } from '../components/PageHeader'
import { Card } from '../components/ui/Card'
import { Loading, StaleNote, Unavailable } from '../components/ui/states'
import { StatTile, StatTiles } from '../components/ui/StatTile'
import type { Tone } from '../components/ui/tones'
import { degrees, LEVEL, type AirLevel } from '../lib/air'
import { formatAgo } from '../lib/format'
import type { Air } from '../lib/types'
import { useApi } from '../lib/useApi'

const CO2_TONE: Record<AirLevel, Tone | undefined> = { fresh: undefined, stuffy: 'warn', open_window: 'down' }

/**
 * Home's Air tab (plan.md M38, 5f), built from Today's Air card: the four readings as cells,
 * then CO₂ as the ring and its last 8 hours, wide.
 */
export function AirPage() {
  const { data: air, error } = useApi<Air>('/api/air', 60_000)
  const now = new Date()

  return (
    <>
      <PageHeader title="Air" subtitle={air ? `${air.room}, from the IKEA ALPSTUGA sensor` : "The living room's air"} />
      {!air && (error ? <Unavailable what="The air sensor" /> : <Loading />)}
      {air && (
        <>
          {!air.available && (
            <p role="status" className="mb-4 text-small text-warn">
              The sensor is not answering: showing its last values.
            </p>
          )}
          <StatTiles label="Readings" count={4}>
            <StatTile
              title="Temperature"
              figure={air.temperature != null ? `${degrees(air.temperature)}°` : '–'}
              sub={air.outside != null ? `${air.outside}° outside` : undefined}
            />
            <StatTile title="Humidity" figure={air.humidity != null ? `${air.humidity}%` : '–'} />
            <StatTile
              title="CO₂"
              figure={air.co2 != null ? `${air.co2} ppm` : '–'}
              tone={air.level ? CO2_TONE[air.level] : undefined}
              sub={air.level ? LEVEL[air.level].word : undefined}
            />
            <StatTile
              title="Fine dust"
              figure={air.pm25 != null ? `${air.pm25} µg/m³` : '–'}
              sub={air.quality ? `Sensor says: ${air.quality}` : 'PM2.5'}
            />
          </StatTiles>

          {air.co2 != null && air.level && (
            <Card title="CO₂, the last 8 hours" note="Dashed: 800 and 1200 ppm">
              <div className="grid items-center gap-6 md:grid-cols-[200px_minmax(0,1fr)]">
                <div className="grid justify-items-center">
                  <Co2Ring ppm={air.co2} level={air.level} />
                  <p className={`-mt-3 text-body font-semibold ${LEVEL[air.level].className}`}>{LEVEL[air.level].word}</p>
                </div>
                <Co2Curve history={air.history} level={air.level} tall />
              </div>
            </Card>
          )}
          <p className="mt-3 text-small text-faint">Updated {formatAgo(air.as_of, now)}</p>
          {air.stale && <StaleNote />}
        </>
      )}
    </>
  )
}
