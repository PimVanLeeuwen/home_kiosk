import { POOL_FULL_PCT } from '../../lib/attention'
import { formatBytes, formatMbit } from '../../lib/format'
import type { Nas } from '../../lib/types'
import { Card, Loading, StaleNote, Unavailable } from './Card'
import { Meter } from './Meter'

interface Props {
  nas: Nas | undefined
  error: Error | undefined
}

export function NasCard({ nas, error }: Props) {
  return (
    <Card title="NAS" link={{ to: '/nas', label: 'Details' }}>
      {!nas && (error ? <Unavailable what="NAS data" /> : <Loading />)}
      {nas && (
        <>
          <div className="grid gap-x-6 gap-y-3.5 sm:grid-cols-2">
            <Meter label="CPU" value={`${Math.round(nas.cpu_pct)}%`} pct={nas.cpu_pct} />
            <Meter label="Memory" value={`${Math.round(nas.ram_pct)}%`} pct={nas.ram_pct} />
            {nas.cpu_temp_c != null && (
              <Meter
                label="CPU temp"
                value={`${Math.round(nas.cpu_temp_c)} °C`}
                pct={nas.cpu_temp_c}
                tone={nas.cpu_temp_c >= 80 ? 'down' : nas.cpu_temp_c >= 70 ? 'warn' : 'ok'}
              />
            )}
            <div className="text-[13px] sm:col-span-2">
              <div className="flex justify-between gap-3">
                <span className="text-muted">Network</span>
                <span>
                  ↓ {formatMbit(nas.network.rx_mbps)} · ↑ {formatMbit(nas.network.tx_mbps)}
                </span>
              </div>
            </div>
          </div>
          <div className="mt-5 space-y-3.5">
            {/* Pools arrive fullest first. */}
            {nas.storage.pools.slice(0, 3).map((pool) => (
              <Meter
                key={pool.name}
                label={pool.name}
                value={`${formatBytes(pool.used_bytes)} / ${formatBytes(pool.total_bytes)}`}
                pct={pool.used_pct}
                tone={pool.used_pct >= 97 ? 'down' : pool.used_pct >= POOL_FULL_PCT ? 'warn' : 'ok'}
              />
            ))}
          </div>
          {nas.stale && <StaleNote />}
        </>
      )}
    </Card>
  )
}
