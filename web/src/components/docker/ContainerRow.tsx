import { ChevronDown } from 'lucide-react'
import { cn } from '../../lib/cn'
import { formatBytes, formatRate, formatWhen } from '../../lib/format'
import { containerStatus } from '../../lib/containers'
import type { ContainerLoad, ContainerPoint, ContainerUpdate } from '../../lib/types'
import { useApi } from '../../lib/useApi'
import { Sparkline } from '../home/Sparkline'
import { StatusDot } from '../StatusDot'
import { MiniSpark } from './MiniSpark'

const pct = (n: number | null) => (n == null ? '–' : `${n < 10 ? n.toFixed(1).replace('.', ',') : Math.round(n)}%`)

interface Props {
  container: ContainerLoad
  spark: (number | null)[]
  updates: ContainerUpdate[]
  open: boolean
  onToggle: () => void
}

export function ContainerRow({ container: c, spark, updates, open, onToggle }: Props) {
  const detailId = `container-${c.name}`
  return (
    <li className="border-t border-line-soft first:border-t-0">
      <button
        type="button"
        aria-expanded={open}
        aria-controls={detailId}
        onClick={onToggle}
        className="grid w-full grid-cols-[minmax(0,1fr)_auto] items-center gap-x-4 gap-y-1 px-1 py-2.5 text-left hover:bg-raised/60 md:grid-cols-[minmax(0,1fr)_5rem_5.5rem_6.5rem_10rem_1rem]"
      >
        <span className="flex min-w-0 items-center gap-2.5">
          <StatusDot status={containerStatus(c)} />
          <span className="min-w-0">
            <span className="block truncate font-mono text-[13px]">{c.name}</span>
            <span className="block truncate text-[11.5px] text-faint">{c.image}</span>
          </span>
        </span>
        <MiniSpark values={spark} label={`${c.name} CPU, last 24 hours`} />
        <span className="text-[13px] md:text-right">
          <span className="text-faint md:sr-only">CPU </span>
          {pct(c.cpu_pct)}
        </span>
        <span className="text-[13px] md:text-right">
          <span className="text-faint md:sr-only">Memory </span>
          {c.mem_bytes == null ? '–' : formatBytes(c.mem_bytes)}
        </span>
        <span className="col-span-2 text-[12.5px] text-muted md:col-span-1 md:text-right">
          {c.rx_bps == null ? (c.state === 'running' ? 'host network' : '–') : `↓ ${formatRate(c.rx_bps)} ↑ ${formatRate(c.tx_bps ?? 0)}`}
        </span>
        <ChevronDown aria-hidden="true" className={cn('hidden size-4 text-faint transition-transform md:block', open && 'rotate-180')} />
      </button>
      {open && <ContainerDetail id={detailId} container={c} updates={updates} />}
    </li>
  )
}

function ContainerDetail({ id, container: c, updates }: { id: string; container: ContainerLoad; updates: ContainerUpdate[] }) {
  const history = useApi<ContainerPoint[]>(`/api/docker/history/${encodeURIComponent(c.name)}`)
  const points = history.data ?? []
  const cpu = points.map((p) => p.cpu ?? 0)
  const mem = points.map((p) => p.mem ?? 0)

  return (
    <div id={id} className="grid gap-5 px-1 pt-1 pb-4 md:grid-cols-2">
      <div>
        <p className="text-[12.5px] text-muted">CPU, last 24 hours (peak {pct(points.length ? Math.max(...cpu) : null)})</p>
        {points.length > 1 ? <Sparkline values={cpu} label={`${c.name} CPU, last 24 hours`} fromZero /> : <p className="py-6 text-[13px] text-faint">No history yet.</p>}
      </div>
      <div>
        <p className="text-[12.5px] text-muted">
          Memory, last 24 hours{c.mem_limit ? ` (limit ${formatBytes(c.mem_limit)})` : ''}
        </p>
        {points.length > 1 ? <Sparkline values={mem} label={`${c.name} memory, last 24 hours`} fromZero /> : <p className="py-6 text-[13px] text-faint">No history yet.</p>}
      </div>
      <dl className="grid grid-cols-[auto_minmax(0,1fr)] gap-x-4 gap-y-1 text-[13px] md:col-span-2">
        <dt className="text-muted">Status</dt>
        <dd>{c.status || c.state}</dd>
        <dt className="text-muted">Image</dt>
        <dd className="truncate font-mono text-[12.5px]">{c.image}</dd>
        <dt className="text-muted">Last update</dt>
        <dd>{updates[0] ? formatWhen(updates[0].at) : 'None seen yet'}</dd>
      </dl>
    </div>
  )
}
