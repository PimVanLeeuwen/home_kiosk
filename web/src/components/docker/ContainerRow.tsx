import type { ReactNode } from 'react'
import { ChevronDown } from 'lucide-react'
import { cn } from '../../lib/cn'
import { formatBytes, formatRate, formatWhen } from '../../lib/format'
import { containerStatus } from '../../lib/containers'
import type { ContainerLoad, ContainerPoint, ContainerUpdate } from '../../lib/types'
import { useApi } from '../../lib/useApi'
import { GlowArea } from '../ui/GlowArea'
import { MiniSparkline } from '../ui/MiniSparkline'
import { StatusDot } from '../StatusDot'

const pct = (n: number | null) => (n == null ? '–' : `${n < 10 ? n.toFixed(1).replace('.', ',') : Math.round(n)}%`)

/** "Exited (0) 1 hour ago" → "exited 1 hour ago"; anything else as Docker wrote it. */
function exited(status: string): string {
  const m = status.match(/^Exited \(\d+\) (.+)$/)
  return m ? `exited ${m[1]}` : status.toLowerCase()
}

/** A thin bar under a figure: its share of the busiest container on the page. */
function LoadBar({ share, color }: { share: number; color: string }) {
  return (
    <span className="mt-1 block h-[3px] overflow-hidden rounded-full bg-raised" aria-hidden="true">
      <span className="block h-full rounded-full" style={{ width: `${Math.min(100, Math.max(0, share * 100))}%`, backgroundColor: color }} />
    </span>
  )
}

interface Props {
  container: ContainerLoad
  spark: (number | null)[]
  updates: ContainerUpdate[]
  open: boolean
  onToggle: () => void
  /** The busiest container's CPU and memory on the page, for the bars. */
  cpuTop: number
  memTop: number
}

export function ContainerRow({ container: c, spark, updates, open, onToggle, cpuTop, memTop }: Props) {
  const detailId = `container-${c.name}`
  const status = containerStatus(c)
  const trouble = status === 'down' || status === 'unhealthy'
  const known = spark.filter((v): v is number => v != null)
  return (
    <li>
      <button
        type="button"
        aria-expanded={open}
        aria-controls={detailId}
        onClick={onToggle}
        className={cn(
          'grid w-full grid-cols-[minmax(0,1fr)_4rem_4.5rem] items-center gap-x-3 gap-y-1 rounded-[10px] px-2.5 py-2.5 text-left hover:bg-white/[0.03] md:grid-cols-[minmax(0,1fr)_5rem_5.5rem_6.5rem_10rem_1rem] md:gap-x-4',
          open && 'bg-white/[0.03]',
          trouble && 'bg-linear-to-r from-down/10 to-transparent to-60%',
        )}
      >
        <span className="flex min-w-0 items-center gap-2.5">
          <StatusDot status={status} />
          <span className="min-w-0">
            <span className="block truncate font-mono text-small">{c.name}</span>
            <span className="block truncate text-label text-faint">{c.image}</span>
          </span>
        </span>
        <span className="hidden w-20 md:block">
          {known.length > 1 && <MiniSparkline values={known} label={`${c.name} CPU, last 24 hours`} min={0} floor={0.5} />}
        </span>
        <span className="text-right text-small">
          <span className="sr-only">CPU </span>
          {pct(c.cpu_pct)}
          {c.cpu_pct != null && <LoadBar share={c.cpu_pct / cpuTop} color="var(--color-accent-line)" />}
        </span>
        <span className="text-right text-small">
          <span className="sr-only">Memory </span>
          {c.mem_bytes == null ? '–' : formatBytes(c.mem_bytes)}
          {c.mem_bytes != null && <LoadBar share={c.mem_bytes / memTop} color="var(--color-data-blue)" />}
        </span>
        <span className="col-span-3 text-caption whitespace-nowrap text-muted md:col-span-1 md:text-right">
          {c.state !== 'running' ? (
            <span className="text-down">{exited(c.status)}</span>
          ) : c.rx_bps == null ? (
            'host network'
          ) : (
            `↓ ${formatRate(c.rx_bps)} ↑ ${formatRate(c.tx_bps ?? 0)}`
          )}
        </span>
        <ChevronDown aria-hidden="true" className={cn('hidden size-4 text-faint transition-transform md:block', open && 'rotate-180')} />
      </button>
      {open && <ContainerDetail id={detailId} container={c} updates={updates} />}
    </li>
  )
}

function Panel({ title, note, children }: { title: string; note: string; children: ReactNode }) {
  return (
    <div className="overflow-hidden rounded-[11px] border border-glass-line bg-glass px-3 pt-2.5">
      <p className="flex justify-between gap-3 text-caption">
        <span className="text-muted">{title}</span>
        <span>{note}</span>
      </p>
      <div className="-mx-3 mt-1.5">{children}</div>
    </div>
  )
}

function ContainerDetail({ id, container: c, updates }: { id: string; container: ContainerLoad; updates: ContainerUpdate[] }) {
  const history = useApi<ContainerPoint[]>(`/api/docker/history/${encodeURIComponent(c.name)}`)
  const points = history.data ?? []
  const cpu = points.map((p) => p.cpu ?? 0)
  const mem = points.map((p) => p.mem ?? 0)
  const empty = <p className="px-3 py-6 text-small text-faint">No history yet.</p>

  return (
    <div id={id} className="grid gap-4 px-2.5 pt-1.5 pb-4 md:grid-cols-2 md:pl-8">
      <Panel title="CPU, last 24 hours" note={`peak ${pct(points.length ? Math.max(...cpu) : null)}`}>
        {points.length > 1 ? <GlowArea values={cpu} label={`${c.name} CPU, last 24 hours`} min={0} peak height={80} /> : empty}
      </Panel>
      <Panel title="Memory, last 24 hours" note={c.mem_limit ? `limit ${formatBytes(c.mem_limit)}` : ''}>
        {points.length > 1 ? (
          <GlowArea values={mem} label={`${c.name} memory, last 24 hours`} min={0} color="var(--color-data-blue)" peak height={80} />
        ) : (
          empty
        )}
      </Panel>
      <dl className="grid grid-cols-[auto_minmax(0,1fr)] gap-x-4 gap-y-1 text-small md:col-span-2">
        <dt className="text-muted">Status</dt>
        <dd>{c.status || c.state}</dd>
        <dt className="text-muted">Image</dt>
        <dd className="truncate font-mono text-caption">{c.image}</dd>
        <dt className="text-muted">Last update</dt>
        <dd>{updates[0] ? formatWhen(updates[0].at) : 'None seen yet'}</dd>
      </dl>
    </div>
  )
}
