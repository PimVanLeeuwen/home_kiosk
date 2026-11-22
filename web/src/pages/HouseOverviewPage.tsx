import { Link } from 'react-router'
import { AttentionList } from '../components/AttentionList'
import { PageHeader } from '../components/PageHeader'
import { AnimatedNumber } from '../components/ui/AnimatedNumber'
import { HealthyLine } from '../components/ui/AttentionRow'
import { BarMeter } from '../components/ui/BarMeter'
import { Cell, CellGrid } from '../components/ui/CellGrid'
import { Pill } from '../components/ui/Pill'
import { Sparkline } from '../components/ui/Sparkline'
import { Loading, Unavailable } from '../components/ui/states'
import { POOL_FULL_PCT } from '../lib/attention'
import { cn } from '../lib/cn'
import { formatBytes, formatWhen } from '../lib/format'
import { incidentPath } from '../lib/incidents'
import { useOpenIncidents } from '../lib/openIncidents'
import { PATHS, alertPath } from '../lib/paths'
import type { AlertMessage, Nas, NasPoint } from '../lib/types'
import { useApi } from '../lib/useApi'

const DAY_MS = 86_400_000
/** Messages about the person, not the house: left out of the house's last 24 hours. */
const PERSONAL = ['portfolio', 'todos', 'reminders', 'briefing', 'train']
const DOT = { ok: 'bg-up', info: 'bg-accent-line', warning: 'bg-warn', error: 'bg-down' } as const
const time = new Intl.DateTimeFormat('en-GB', { hour: '2-digit', minute: '2-digit' })

const series = (points: NasPoint[], key: 'cpu' | 'ram' | 'rx_mbps') =>
  points.map((p) => p[key]).filter((v): v is number => v != null)

/** A cell's large light figure, with a smaller unit beside it. */
function Figure({ value, unit, format }: { value: number; unit: string; format?: (n: number) => string }) {
  return (
    <p className="text-display leading-none font-medium tracking-[-0.04em]">
      <AnimatedNumber value={value} format={format} />
      <span className="ml-1 text-heading font-normal tracking-normal text-muted">{unit}</span>
    </p>
  )
}

/** House's overview (plan.md M38): what needs a look in the house, the rest in one line, then its vital signs as cells. */
export function HouseOverviewPage() {
  const nas = useApi<Nas>('/api/nas', 60_000)
  const history = useApi<NasPoint[]>('/api/nas/history', 300_000)
  const messages = useApi<AlertMessage[]>('/api/alerts/messages?limit=40', 60_000)
  const { open } = useOpenIncidents()
  const now = new Date()
  const n = nas.data
  const points = history.data ?? []
  const here = open.filter((i) => incidentPath(i).startsWith(`${PATHS.house}/`))
  const days = n?.uptime_seconds ? Math.floor(n.uptime_seconds / DAY_MS / 1000) : null
  const recent = (messages.data ?? [])
    .filter((m) => !PERSONAL.includes(m.category) && now.getTime() - new Date(m.ts).getTime() < DAY_MS)
    .slice(0, 6)

  const healthy =
    n &&
    [
      n.disks.every((d) => d.smart === 'ok') && `${n.disks.length} disks healthy`,
      `${n.containers.running} of ${n.containers.total} containers running`,
      n.backup.status === 'ok' && n.backup.at && `last backup ${formatWhen(n.backup.at, now)}`,
    ]
      .filter(Boolean)
      .join(', ')

  return (
    <>
      <PageHeader
        title="House"
        subtitle={n ? `${n.host}${days != null ? ` · up ${days} day${days === 1 ? '' : 's'}` : ''}` : 'The NAS, its apps and backups'}
        status={here.length ? <Pill tone={here.some((i) => i.severity === 'error') ? 'down' : 'warn'}>{here.length} to look at</Pill> : <Pill tone="up">All running</Pill>}
      />

      <AttentionList incidents={here} here={PATHS.house} now={now} />
      {healthy && (
        <div className="mb-6">
          <HealthyLine>{`${here.length ? 'The rest is fine' : 'All quiet'}: ${healthy}.`}</HealthyLine>
        </div>
      )}

      {!n && (nas.error ? <Unavailable what="NAS data" /> : <Loading what="the house" />)}

      {n && (
        <CellGrid label="The house at a glance" columns={4}>
          <Cell title="CPU" note={n.cpu_temp_c != null ? `${Math.round(n.cpu_temp_c)} °C` : undefined} className="pb-3">
            <Figure value={n.cpu_pct} unit="%" format={(v) => String(Math.round(v))} />
            <Sparkline values={series(points, 'cpu')} label="CPU, last 24 hours" floor={20} min={0} className="mt-4" />
          </Cell>
          <Cell title="Memory" note={n.mem_total_bytes ? `of ${formatBytes(n.mem_total_bytes)}` : undefined} className="pb-3">
            <Figure value={n.ram_pct} unit="%" format={(v) => String(Math.round(v))} />
            <Sparkline values={series(points, 'ram')} label="Memory, last 24 hours" tone="up" min={0} floor={100} className="mt-4" />
          </Cell>
          <Cell title="Containers" link={{ to: PATHS.docker, label: 'Docker' }}>
            <Figure value={n.containers.running} unit={`/ ${n.containers.total}`} />
            <p className="mt-2 text-small text-muted">{n.containers.running === n.containers.total ? 'running' : `${n.containers.total - n.containers.running} stopped`}</p>
          </Cell>
          <Cell title="Network" note="down" className="pb-3">
            <Figure value={n.network.rx_mbps} unit="Mbit/s" format={(v) => v.toLocaleString('nl-NL', { maximumFractionDigits: 1 })} />
            <Sparkline values={series(points, 'rx_mbps')} label="Network down, last 24 hours" min={0} floor={5} className="mt-4" />
          </Cell>

          <Cell title={`Storage · ${n.storage.used_pct.toFixed(0)}% used`} link={{ to: PATHS.nas, label: 'NAS' }} span={2}>
            <ul className="grid gap-3">
              {[...n.storage.pools]
                .sort((a, b) => b.used_pct - a.used_pct)
                .map((pool) => (
                  <li key={pool.name}>
                    <BarMeter
                      label={pool.name}
                      value={`${formatBytes(pool.used_bytes)} of ${formatBytes(pool.total_bytes)} · ${Math.round(pool.used_pct)}%`}
                      pct={pool.used_pct}
                      tone={pool.used_pct >= POOL_FULL_PCT ? 'warn' : 'accent'}
                    />
                  </li>
                ))}
            </ul>
          </Cell>
          <Cell title="Last 24 hours" link={{ to: PATHS.alerts, label: 'Alerts' }} span={2}>
            {recent.length === 0 ? (
              <p className="text-muted">{messages.data ? 'Nothing sent about the house.' : 'Loading…'}</p>
            ) : (
              <ul>
                {recent.map((m) => (
                  <li key={m.id} className="border-t border-line-soft first:border-t-0">
                    <Link to={alertPath(m.id)} className="grid min-h-11 grid-cols-[0.5rem_1fr_auto] items-center gap-3 text-small hover:text-accent-fg">
                      <span aria-hidden="true" className={cn('size-2 rounded-full', DOT[m.severity])} />
                      <span className="truncate">{m.title}</span>
                      <span className="text-muted">{time.format(new Date(m.ts))}</span>
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </Cell>
        </CellGrid>
      )}
    </>
  )
}
