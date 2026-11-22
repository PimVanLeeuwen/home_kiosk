import { formatAgo } from '../../lib/format'
import type { Air } from '../../lib/types'
import { useApi } from '../../lib/useApi'
import { Card } from '../ui/Card'
import { Loading, StaleNote, Unavailable } from '../ui/states'
import { Co2Curve, Co2Ring } from '../air/Co2'
import { degrees, LEVEL } from '../../lib/air'
import { PATHS } from '../../lib/paths'

/** The living room's air on Home, the Home panel's Air card (plan.md M17). */
export function AirCard() {
  const { data: air, error } = useApi<Air>('/api/air', 60_000)
  const now = new Date()
  const outside = air?.outside != null ? ` · outside ${air.outside}°` : ''

  return (
    <Card
      title="Air"
      link={{ to: PATHS.air, label: 'Details' }}
      note={
        air && (
          <>
            {air.room}
            {outside}
          </>
        )
      }
    >
      {!air && (error ? <Unavailable what="The air sensor" /> : <Loading />)}
      {air && (
        <>
          <div className="grid grid-cols-[minmax(0,1fr)_130px] items-center gap-4 sm:grid-cols-[minmax(0,1fr)_170px]">
            <div className="min-w-0">
              <p className="text-hero leading-none font-semibold tracking-tight tabular-nums">
                {air.temperature != null ? `${degrees(air.temperature)}°` : '–'}
              </p>
              <ul className="mt-3 grid gap-1 text-small text-muted">
                {air.humidity != null && (
                  <li>
                    <span className="font-semibold text-fg">{air.humidity}%</span> humidity
                  </li>
                )}
                {air.pm25 != null && (
                  <li>
                    <span className="font-semibold text-fg">{air.pm25}</span> µg/m³ fine dust
                    {air.quality && <span className="block text-small text-faint">Sensor says: {air.quality}</span>}
                  </li>
                )}
              </ul>
            </div>
            {air.co2 != null && air.level && (
              <div className="grid justify-items-center">
                <Co2Ring ppm={air.co2} level={air.level} />
                <p className={`-mt-3 text-body font-semibold ${LEVEL[air.level].className}`}>{LEVEL[air.level].word}</p>
              </div>
            )}
          </div>
          {air.level && <Co2Curve history={air.history} level={air.level} />}
          {!air.available && <p className="mt-3 text-small text-warn">The sensor is not answering: showing its last values.</p>}
          <p className="mt-3 text-small text-faint">Updated {formatAgo(air.as_of, now)} · IKEA ALPSTUGA</p>
          {air.stale && <StaleNote />}
        </>
      )}
    </Card>
  )
}
