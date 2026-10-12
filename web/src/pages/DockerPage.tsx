import { Search } from 'lucide-react'
import { useState } from 'react'
import { ContainerRow } from '../components/docker/ContainerRow'
import { DockerTiles } from '../components/docker/DockerTiles'
import { Card, Loading, StaleNote, Unavailable } from '../components/home/Card'
import { PageHeader } from '../components/PageHeader'
import { Pill } from '../components/ui/Pill'
import { cn } from '../lib/cn'
import { containerStatus } from '../lib/containers'
import { formatWhen } from '../lib/format'
import type { ContainerLoad, ContainerUpdate, DockerOverview, Nas, Sparklines } from '../lib/types'
import { useApi } from '../lib/useApi'

type Order = 'stack' | 'cpu' | 'memory' | 'name'

const ORDERS: Record<Order, string> = {
  stack: 'By stack',
  cpu: 'CPU',
  memory: 'Memory',
  name: 'Name',
}

function sortRows(rows: ContainerLoad[], order: Order): ContainerLoad[] {
  const by = {
    stack: (a: ContainerLoad, b: ContainerLoad) => a.name.localeCompare(b.name),
    name: (a: ContainerLoad, b: ContainerLoad) => a.name.localeCompare(b.name),
    cpu: (a: ContainerLoad, b: ContainerLoad) => (b.cpu_pct ?? -1) - (a.cpu_pct ?? -1),
    memory: (a: ContainerLoad, b: ContainerLoad) => (b.mem_bytes ?? -1) - (a.mem_bytes ?? -1),
  }[order]
  return [...rows].sort(by)
}

const shortId = (id: string) => id.replace(/^sha256:/, '').slice(0, 12)

export function DockerPage() {
  const overview = useApi<DockerOverview>('/api/docker', 60_000)
  const sparks = useApi<Sparklines>('/api/docker/sparklines', 300_000)
  const updates = useApi<ContainerUpdate[]>('/api/docker/updates', 300_000)
  const nas = useApi<Nas>('/api/nas', 300_000)
  const [order, setOrder] = useState<Order>('stack')
  const [query, setQuery] = useState('')
  const [open, setOpen] = useState<string | null>(null)

  const all = overview.data?.containers ?? []
  const running = all.filter((c) => c.state === 'running').length
  const q = query.trim().toLowerCase()
  const rows = sortRows(all.filter((c) => !q || `${c.name} ${c.image} ${c.project ?? ''}`.toLowerCase().includes(q)), order)
  const updatesFor = (name: string) => (updates.data ?? []).filter((u) => u.name === name)
  const needLook = all.filter((c) => ['down', 'unhealthy'].includes(containerStatus(c))).length

  const groups: [string, ContainerLoad[]][] =
    order === 'stack'
      ? Object.entries(
          rows.reduce<Record<string, ContainerLoad[]>>((acc, c) => {
            const stack = c.project ?? 'No stack'
            ;(acc[stack] ??= []).push(c)
            return acc
          }, {}),
        ).sort(([a], [b]) => a.localeCompare(b))
      : [['Containers', rows]]

  const renderRows = (list: ContainerLoad[]) => (
    <ul>
      {list.map((c) => (
        <ContainerRow
          key={c.name}
          container={c}
          spark={sparks.data?.[c.name] ?? []}
          updates={updatesFor(c.name)}
          open={open === c.name}
          onToggle={() => setOpen((v) => (v === c.name ? null : c.name))}
        />
      ))}
    </ul>
  )

  return (
    <>
      <PageHeader
        title="Docker"
        subtitle={overview.data ? `${running} of ${all.length} running` : 'Containers, their load and update history'}
        actions={
          overview.data &&
          (needLook ? <Pill tone="warn">{needLook} need{needLook === 1 ? 's' : ''} a look</Pill> : <Pill tone="up">All running</Pill>)
        }
      />

      {!overview.data && (overview.error ? <Unavailable what="Container data" /> : <Loading />)}

      {overview.data && (
        <>
          <DockerTiles overview={overview.data} updates={updates.data ?? []} memTotal={nas.data?.mem_total_bytes} />

          <div className="mb-4 flex flex-wrap items-center gap-3">
            <label className="flex min-w-0 flex-1 basis-64 items-center gap-2 rounded-[11px] border border-glass-line bg-glass px-3 py-2 text-muted focus-within:border-accent-line">
              <Search aria-hidden="true" className="size-4 shrink-0" />
              <span className="sr-only">Filter containers</span>
              <input
                type="search"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Filter by name, image or stack"
                className="min-w-0 flex-1 bg-transparent text-fg placeholder:text-faint focus:outline-none"
              />
            </label>
            <div
              role="radiogroup"
              aria-label="Order"
              className="flex w-full gap-0.5 rounded-[11px] border border-glass-line bg-glass p-[3px] text-[12.5px] sm:w-auto"
            >
              {(Object.entries(ORDERS) as [Order, string][]).map(([value, label]) => (
                <button
                  key={value}
                  type="button"
                  role="radio"
                  aria-checked={order === value}
                  onClick={() => setOrder(value)}
                  className={cn(
                    'flex-1 rounded-[8px] px-2.5 py-1.5 whitespace-nowrap sm:flex-none',
                    order === value ? 'bg-accent/20 text-fg shadow-[inset_0_0_0_1px_rgb(143_128_255/0.4)]' : 'text-muted hover:text-fg',
                  )}
                >
                  {label}
                </button>
              ))}
            </div>
          </div>

          <Card title="Containers">
            {order === 'stack'
              ? groups.map(([stack, list]) => {
                  const up = list.filter((c) => containerStatus(c) === 'up').length
                  // One card with stacks as headed sections: most stacks hold one container.
                  return (
                    <section key={stack} aria-label={`${stack} · ${up}/${list.length}`} className="mt-4 first:mt-0">
                      <h3 className="mb-1 px-1 text-[11px] font-semibold tracking-[0.08em] text-faint uppercase">
                        {stack}{' '}
                        <span className="font-normal tracking-normal normal-case">
                          · {up}/{list.length}
                        </span>
                      </h3>
                      {renderRows(list)}
                    </section>
                  )
                })
              : renderRows(rows)}
            {rows.length === 0 && <p className="text-muted">No containers match “{query}”.</p>}
          </Card>
          {overview.data.stale && <StaleNote />}

          <Card title="Image updates" className="mt-5">
            {(updates.data ?? []).length === 0 ? (
              <p className="text-muted">
                No updates seen yet. The hub notices when Watchtower or Dockge recreates a container from a new image.
              </p>
            ) : (
              <ul>
                {(updates.data ?? []).slice(0, 25).map((u) => (
                  <li key={`${u.at}-${u.name}`} className="flex flex-wrap items-baseline gap-x-3 gap-y-0.5 border-t border-line-soft py-2 first:border-t-0 text-[13px]">
                    <span className="w-36 shrink-0 text-faint">{formatWhen(u.at)}</span>
                    <span className="font-mono">{u.name}</span>
                    <span className="min-w-0 flex-1 truncate text-muted">{u.image}</span>
                    <span className="font-mono text-[12px] text-faint">
                      {shortId(u.old_image_id)} → {shortId(u.new_image_id)}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </Card>
        </>
      )}
    </>
  )
}
