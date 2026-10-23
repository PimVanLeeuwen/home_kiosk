import { Loading, StaleNote, Unavailable } from '../components/ui/states'
import { DisksCard } from '../components/nas/DisksCard'
import { InstrumentCard } from '../components/nas/InstrumentCard'
import { StorageCard } from '../components/nas/StorageCard'
import { ExposureCard } from '../components/nas/ExposureCard'
import { UpsCard } from '../components/nas/UpsCard'
import { PageHeader } from '../components/PageHeader'
import { Pill } from '../components/ui/Pill'
import { formatBytes, formatMbit } from '../lib/format'
import { HOT_CPU_C, nasNeedsLook, WARM_CPU_C } from '../lib/nasHealth'
import type { Nas, NasPoint } from '../lib/types'
import { useApi } from '../lib/useApi'

/** The figure of formatMbit without its unit, which the Network card sets smaller. */
const mbit = (n: number) => formatMbit(n).replace(/ Mbit\/s$/, '')

/**
 * The top of a percentage chart: a fifth above the day's peak, so its shape
 * reads, but never below `floor`, so an idle NAS does not look busy.
 */
const headroom = (top: number | null, floor = 10) => Math.min(100, Math.max(floor, (top ?? 0) * 1.2))
/** Temperatures start here rather than at 0 °C, which would leave a solid block. */
const TEMP_FLOOR_C = 20

/** The temperature line when all is well: a cool blue rather than the accent. */
const COOL = '#7cc4ff'

function peak(points: NasPoint[], key: 'cpu' | 'ram' | 'temp' | 'rx_mbps' | 'tx_mbps'): number | null {
  const values = points.map((p) => p[key]).filter((v): v is number => v != null)
  return values.length ? Math.max(...values) : null
}


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
        status={n && (nasNeedsLook(n) ? <Pill tone="warn">Needs a look</Pill> : <Pill tone="up">Healthy</Pill>)}
      />

      {!n && (nas.error ? <Unavailable what="NAS data" /> : <Loading />)}

      {n && (
        <>
          <div className="grid grid-cols-2 gap-2.5 md:gap-4 xl:grid-cols-4">
            <InstrumentCard
              title="CPU"
              now={`${Math.round(n.cpu_pct)}%`}
              detail={peak(points, 'cpu') != null && `Peak ${Math.round(peak(points, 'cpu')!)}% in 24 hours`}
              values={points.map((p) => p.cpu)}
              label="CPU, last 24 hours"
              max={headroom(peak(points, 'cpu'))}
            />
            <InstrumentCard
              title="Memory"
              now={`${Math.round(n.ram_pct)}%`}
              detail={memUsed != null && n.mem_total_bytes ? `${formatBytes(memUsed)} of ${formatBytes(n.mem_total_bytes)}` : undefined}
              values={points.map((p) => p.ram)}
              label="Memory, last 24 hours"
              max={headroom(peak(points, 'ram'))}
            />
            <InstrumentCard
              title="CPU temperature"
              now={n.cpu_temp_c != null ? `${Math.round(n.cpu_temp_c)} °C` : '–'}
              detail={peak(points, 'temp') != null && `Peak ${Math.round(peak(points, 'temp')!)} °C in 24 hours`}
              values={points.map((p) => p.temp)}
              label="CPU temperature, last 24 hours"
              min={TEMP_FLOOR_C}
              tone={n.cpu_temp_c == null ? undefined : n.cpu_temp_c >= HOT_CPU_C ? 'down' : n.cpu_temp_c >= WARM_CPU_C ? 'warn' : undefined}
              color={COOL}
            />
            <InstrumentCard
              title="Network"
              now={
                <>
                  ↓ {mbit(n.network.rx_mbps)}
                  <span className="text-[0.55em] font-medium text-muted"> Mbit/s</span>
                </>
              }
              detail={`↑ ${formatMbit(n.network.tx_mbps)} now`}
              values={points.map((p) => p.rx_mbps)}
              label="Network download and upload, last 24 hours"
              secondary={{ values: points.map((p) => p.tx_mbps), label: 'up', primaryLabel: 'down' }}
            />
          </div>

          <div className="mt-5 grid gap-5 lg:grid-cols-[1.4fr_1fr]">
            <StorageCard pools={n.storage.pools} />
            <DisksCard nas={n} />
          </div>
          <div className="mt-5 grid gap-5 lg:grid-cols-2">
            <UpsCard />
            <ExposureCard />
          </div>
          {n.stale && <StaleNote />}
        </>
      )}
    </>
  )
}
