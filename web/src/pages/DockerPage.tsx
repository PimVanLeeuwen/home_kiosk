import { useState } from 'react'
import { ContainerRow } from '../components/docker/ContainerRow'
import { DockerTiles } from '../components/docker/DockerTiles'
import { UpdatesCard } from '../components/docker/UpdatesCard'
import { Card } from '../components/ui/Card'
import { Loading, StaleNote, Unavailable } from '../components/ui/states'
import { PageHeader } from '../components/PageHeader'
import { Pill } from '../components/ui/Pill'
import { cn } from '../lib/cn'
import { containerStatus } from '../lib/containers'
import type { ContainerLoad, ContainerUpdate, DockerOverview, Nas, Sparklines } from '../lib/types'
import { useApi } from '../lib/useApi'
import { SearchField } from '../components/ui/SearchField'
import { Segmented } from '../components/ui/Segmented'

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
  // The bars in each row compare against the busiest container.
  const cpuTop = Math.max(0.5, ...all.map((c) => c.cpu_pct ?? 0))
  const memTop = Math.max(1, ...all.map((c) => c.mem_bytes ?? 0))
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
          cpuTop={cpuTop}
          memTop={memTop}
        />
      ))}
    </ul>
  )

  return (
    <>
      <PageHeader
        title="Docker"
        subtitle={overview.data ? `${running} of ${all.length} running` : 'Containers, their load and update history'}
        status={
          overview.data &&
          (needLook ? <Pill tone="warn">{needLook} need{needLook === 1 ? 's' : ''} a look</Pill> : <Pill tone="up">All running</Pill>)
        }
      />

      {!overview.data && (overview.error ? <Unavailable what="Container data" /> : <Loading />)}

      {overview.data && (
        <>
          <DockerTiles overview={overview.data} updates={updates.data ?? []} memTotal={nas.data?.mem_total_bytes} />

          <div className="mb-4 flex flex-wrap items-center gap-3">
            <SearchField
              label="Filter containers"
              value={query}
              onChange={setQuery}
              placeholder="Filter by name, image or stack"
              className="flex-1 basis-64"
            />
            <Segmented label="Order" options={Object.entries(ORDERS) as [Order, string][]} value={order} onChange={setOrder} stretch />
          </div>

          <Card title="Containers">
            {order === 'stack'
              ? groups.map(([stack, list]) => {
                  const up = list.filter((c) => containerStatus(c) === 'up').length
                  const stopped = list.some((c) => containerStatus(c) === 'down')
                  // One card with stacks as headed sections: most stacks hold one container.
                  return (
                    <section key={stack} aria-label={`${stack} · ${up}/${list.length}`} className="mt-4 first:mt-0">
                      <h3 className="mb-1 flex items-center gap-2 px-2.5 text-[11px] font-semibold tracking-[0.08em] text-faint uppercase">
                        {stack}
                        <span
                          data-tone={up === list.length ? 'up' : stopped ? 'down' : 'warn'}
                          className={cn(
                            'rounded-[6px] px-1.5 text-[10.5px] tracking-normal normal-case',
                            up === list.length ? 'bg-up/13 text-up' : stopped ? 'bg-down/14 text-down' : 'bg-warn/15 text-warn',
                          )}
                        >
                          {up}/{list.length}
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

          <UpdatesCard updates={updates.data ?? []} />
        </>
      )}
    </>
  )
}
