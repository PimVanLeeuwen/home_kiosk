import { POOL_FULL_PCT } from '../../lib/attention'
import { cn } from '../../lib/cn'
import { formatBytes, formatMbit, formatRunway } from '../../lib/format'
import type { Nas, NasPoint, Ups } from '../../lib/types'
import { useApi } from '../../lib/useApi'
import { ArcGauge } from '../ui/ArcGauge'
import { GlassTile } from '../ui/GlassTile'
import { GlowDot } from '../ui/GlowDot'
import { MiniSparkline } from '../ui/MiniSparkline'
import { Pill } from '../ui/Pill'
import { Card, Loading, StaleNote, Unavailable } from './Card'
import { Meter } from './Meter'

/** A runway shorter than this is worth a look. */
const SHORT_RUNWAY_MONTHS = 6
const HOT_CPU_C = 80

const UPS_LABEL: Record<Ups['status'], string> = {
  online: 'on mains',
  on_battery: 'on battery',
  low_battery: 'battery low',
  unknown: 'unknown',
}

const series = (points: NasPoint[] | undefined, key: 'cpu' | 'ram') =>
  (points ?? []).map((p) => p[key]).filter((v): v is number => v != null)

interface Props {
  nas: Nas | undefined
  error: Error | undefined
}

/** The NAS as an instrument: the fullest pool on a dial, load as glowing lines, a dot per disk. */
export function NasCard({ nas, error }: Props) {
  const history = useApi<NasPoint[]>('/api/nas/history', 300_000)
  const { data: ups } = useApi<Ups>('/api/ups', 60_000)

  // Pools arrive fullest first.
  const [fullest, ...others] = nas?.storage.pools ?? []
  const badDisks = nas?.disks.filter((d) => d.smart !== 'ok') ?? []
  const needsLook =
    !!nas &&
    ((fullest?.used_pct ?? 0) >= POOL_FULL_PCT || badDisks.length > 0 || (nas.cpu_temp_c ?? 0) >= HOT_CPU_C)
  const shortRunway = fullest?.projection_months != null && fullest.projection_months < SHORT_RUNWAY_MONTHS
  const hottest = Math.max(...(nas?.disks.map((d) => d.temp_c ?? 0) ?? [0]))

  return (
    <Card
      title="NAS"
      link={{ to: '/nas', label: 'Details' }}
      actions={nas && <Pill tone={needsLook ? 'warn' : 'up'}>{needsLook ? 'Needs a look' : 'Healthy'}</Pill>}
    >
      {!nas && (error ? <Unavailable what="NAS data" /> : <Loading />)}
      {nas && (
        <div className="grid gap-3.5">
          {fullest && (
            <ArcGauge pct={fullest.used_pct} alertAt={POOL_FULL_PCT} label={fullest.name}>
              <p className="text-muted">
                {fullest.name} · {formatBytes(fullest.used_bytes)} of {formatBytes(fullest.total_bytes)}
              </p>
              <p className={shortRunway ? 'text-warn' : 'text-faint'}>{formatRunway(fullest.projection_months)}</p>
            </ArcGauge>
          )}

          <div className="grid grid-cols-3 gap-2.5">
            <GlassTile
              label={nas.cpu_temp_c != null ? `CPU · ${Math.round(nas.cpu_temp_c)} °C` : 'CPU'}
              value={`${Math.round(nas.cpu_pct)}%`}
            >
              <MiniSparkline values={series(history.data, 'cpu')} label="CPU, last 24 hours" />
            </GlassTile>
            <GlassTile label="Memory" value={`${Math.round(nas.ram_pct)}%`}>
              <MiniSparkline values={series(history.data, 'ram')} label="Memory, last 24 hours" />
            </GlassTile>
            <GlassTile label={hottest > 0 ? `Disks · ${hottest} °C` : 'Disks'} value={`${nas.disks.length - badDisks.length} of ${nas.disks.length}`}>
              <span className="flex h-5 items-center gap-[5px]">
                {nas.disks.map((d) => (
                  <GlowDot
                    key={d.name}
                    tone={d.smart === 'fail' ? 'down' : d.smart === 'warn' ? 'warn' : 'up'}
                    label={`${d.name}: ${d.smart === 'ok' ? 'healthy' : d.smart === 'warn' ? 'SMART warnings' : 'failing'}`}
                    className="size-[7px]"
                  />
                ))}
              </span>
            </GlassTile>
          </div>

          {others.length > 0 && (
            <div className="space-y-2.5">
              {others.slice(0, 2).map((pool) => (
                <Meter
                  key={pool.name}
                  label={pool.name}
                  value={`${formatBytes(pool.used_bytes)} / ${formatBytes(pool.total_bytes)}`}
                  pct={pool.used_pct}
                  tone={pool.used_pct >= 97 ? 'down' : pool.used_pct >= POOL_FULL_PCT ? 'warn' : 'ok'}
                />
              ))}
            </div>
          )}

          <div className="flex flex-wrap justify-between gap-x-4 gap-y-1 border-t border-line-soft pt-2.5 text-[12.5px] text-muted">
            <span>
              Network ↓ {formatMbit(nas.network.rx_mbps)} · ↑ {formatMbit(nas.network.tx_mbps)}
            </span>
            {ups && (
              <span className={cn(ups.status !== 'online' && ups.status !== 'unknown' && 'text-warn')}>
                UPS {UPS_LABEL[ups.status]}
                {ups.charge != null && ` · ${Math.round(ups.charge)}%`}
              </span>
            )}
          </div>
          {nas.stale && <StaleNote />}
        </div>
      )}
    </Card>
  )
}
