import { Link } from 'react-router'
import { Card, Loading, StaleNote, Unavailable } from '../components/home/Card'
import { Meter } from '../components/home/Meter'
import { ChartCard } from '../components/nas/ChartCard'
import { PageHeader } from '../components/PageHeader'
import { POOL_FULL_PCT } from '../lib/attention'
import { cn } from '../lib/cn'
import { formatBytes, formatMbit, formatRunway } from '../lib/format'
import type { Nas, NasPoint } from '../lib/types'
import { useApi } from '../lib/useApi'

const one = (n: number) => n.toFixed(1).replace('.', ',')

function peak(points: NasPoint[], key: 'cpu' | 'ram' | 'temp' | 'rx_mbps' | 'tx_mbps'): number | null {
  const values = points.map((p) => p[key]).filter((v): v is number => v != null)
  return values.length ? Math.max(...values) : null
}

const SMART = {
  ok: { label: 'Healthy', className: 'text-up' },
  warn: { label: 'Warnings', className: 'text-warn' },
  fail: { label: 'Failing', className: 'text-down' },
} as const

export function NasPage() {
  const nas = useApi<Nas>('/api/nas', 60_000)
  const history = useApi<NasPoint[]>('/api/nas/history', 300_000)
  const points = history.data ?? []
  const n = nas.data

  const days = n?.uptime_seconds ? Math.floor(n.uptime_seconds / 86_400) : null
  const memUsed = n?.mem_total_bytes ? (n.ram_pct / 100) * n.mem_total_bytes : null

  return (
    <>
      <PageHeader
        title="NAS"
        subtitle={n ? `${n.host}${days != null ? ` · up ${days} day${days === 1 ? '' : 's'}` : ''}` : 'CPU, memory, storage and disk health'}
      />

      {!n && (nas.error ? <Unavailable what="NAS data" /> : <Loading />)}

      {n && (
        <>
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <ChartCard
              title="CPU"
              now={`${Math.round(n.cpu_pct)}%`}
              detail={peak(points, 'cpu') != null && `Peak ${Math.round(peak(points, 'cpu')!)}% in 24 hours`}
              values={points.map((p) => p.cpu)}
              label="CPU, last 24 hours"
              max={100}
            />
            <ChartCard
              title="Memory"
              now={`${Math.round(n.ram_pct)}%`}
              detail={memUsed != null && n.mem_total_bytes ? `${formatBytes(memUsed)} of ${formatBytes(n.mem_total_bytes)}` : undefined}
              values={points.map((p) => p.ram)}
              label="Memory, last 24 hours"
              max={100}
            />
            <ChartCard
              title="CPU temperature"
              now={n.cpu_temp_c != null ? `${Math.round(n.cpu_temp_c)} °C` : '–'}
              detail={peak(points, 'temp') != null && `Peak ${Math.round(peak(points, 'temp')!)} °C in 24 hours`}
              values={points.map((p) => p.temp)}
              label="CPU temperature, last 24 hours"
            />
            <ChartCard
              title="Network"
              now={`↓ ${formatMbit(n.network.rx_mbps)}`}
              detail={`↑ ${formatMbit(n.network.tx_mbps)} now`}
              values={points.map((p) => p.rx_mbps)}
              label="Network download, last 24 hours"
            />
          </div>

          <div className="mt-5 grid gap-5 lg:grid-cols-[1.4fr_1fr]">
            <Card title="Storage">
              <ul className="space-y-4">
                {/* Pools arrive fullest first. */}
                {n.storage.pools.map((pool) => (
                  <li key={pool.name}>
                    <Meter
                      label={pool.name}
                      value={`${formatBytes(pool.used_bytes)} / ${formatBytes(pool.total_bytes)}`}
                      pct={pool.used_pct}
                      tone={pool.used_pct >= 97 ? 'down' : pool.used_pct >= POOL_FULL_PCT ? 'warn' : 'ok'}
                    />
                    <p className="mt-1 flex justify-between gap-3 text-[12px] text-faint">
                      <span>
                        {one(pool.used_pct)}% used · {formatBytes(pool.free_bytes)} free
                      </span>
                      <span>{formatRunway(pool.projection_months)}</span>
                    </p>
                  </li>
                ))}
              </ul>
            </Card>

            <Card title="Disks">
              {n.disks.length === 0 ? (
                <p className="text-muted">No disk data from Scrutiny.</p>
              ) : (
                <table className="w-full text-[13.5px]">
                  <caption className="sr-only">Disk temperature and SMART health, from Scrutiny</caption>
                  <thead>
                    <tr className="text-left text-[12px] text-faint">
                      <th className="pb-2 font-medium">Disk</th>
                      <th className="pb-2 text-right font-medium">Temperature</th>
                      <th className="pb-2 text-right font-medium">SMART</th>
                    </tr>
                  </thead>
                  <tbody>
                    {n.disks.map((disk) => (
                      <tr key={disk.name} className="border-t border-line-soft">
                        <td className="py-2 font-mono text-[12.5px]">{disk.name}</td>
                        <td className={cn('py-2 text-right', disk.temp_c != null && disk.temp_c >= 50 && 'text-warn')}>
                          {disk.temp_c != null ? `${Math.round(disk.temp_c)} °C` : '–'}
                        </td>
                        <td className={cn('py-2 text-right font-medium', SMART[disk.smart].className)}>{SMART[disk.smart].label}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
              <p className="mt-4 text-[12.5px] text-muted">
                Containers: {n.containers.running} of {n.containers.total} running.{' '}
                <Link to="/docker" className="text-accent-fg hover:underline">
                  Open Docker
                </Link>
              </p>
            </Card>
          </div>
          {n.stale && <StaleNote />}
        </>
      )}
    </>
  )
}
