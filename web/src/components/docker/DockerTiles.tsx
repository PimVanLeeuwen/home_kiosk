import { cn } from '../../lib/cn'
import { containerStatus } from '../../lib/containers'
import { formatBytes } from '../../lib/format'
import type { ContainerLoad, ContainerUpdate, DockerOverview } from '../../lib/types'
import { OutOf, StatTile, StatTiles } from '../ui/StatTile'

const pct = (n: number) => `${n.toFixed(1).replace('.', ',')}%`
/** Colours for the biggest memory users; the rest is grey. */
const MEMORY_COLOURS = ['#8f80ff', '#7cc4ff', '#7fe0b0']
const DAY = 86_400_000
const weekday = new Intl.DateTimeFormat('en-GB', { weekday: 'narrow' })

interface Props {
  overview: DockerOverview
  updates: ContainerUpdate[]
  /** The NAS's memory, for "of 32 GB"; left out when unknown. */
  memTotal?: number | null
}

/** Running, CPU, memory and updates as four small instruments at the top of the Docker page. */
export function DockerTiles({ overview, updates, memTotal }: Props) {
  const all = overview.containers
  const running = all.filter((c) => c.state === 'running').length
  const busiest = [...all].filter((c) => c.cpu_pct != null).sort((a, b) => b.cpu_pct! - a.cpu_pct!).slice(0, 3)
  const biggest = [...all].filter((c) => c.mem_bytes != null).sort((a, b) => b.mem_bytes! - a.mem_bytes!).slice(0, 3)
  const memTop = Math.max(overview.mem_bytes, 1)

  // Days counted back from the snapshot's own time, so rendering stays pure.
  const end = new Date(overview.as_of).getTime()
  const days = Array.from({ length: 7 }, (_, i) => {
    const from = end - (7 - i) * DAY
    return {
      label: weekday.format(new Date(from + DAY)),
      count: updates.filter((u) => {
        const at = new Date(u.at).getTime()
        return at > from && at <= from + DAY
      }).length,
    }
  })
  const recent = days.reduce((sum, d) => sum + d.count, 0)

  return (
    <StatTiles label="Summary" count={4}>
      <StatTile
        title="Running"
        figure={<OutOf n={running} of={all.length} />}
      >
        <p className="mt-2.5 flex flex-wrap gap-1" aria-hidden="true">
          {all.map((c: ContainerLoad) => {
            const status = containerStatus(c)
            return (
              <i
                key={c.name}
                title={c.name}
                className={cn(
                  'block size-[7px] rounded-full',
                  status === 'up' && 'bg-up shadow-[0_0_5px_rgb(63_185_127/0.7)]',
                  (status === 'unhealthy' || status === 'starting') && 'bg-warn shadow-[0_0_6px_var(--color-warn)]',
                  status === 'down' && 'bg-down shadow-[0_0_6px_var(--color-down)]',
                )}
              />
            )
          })}
        </p>
      </StatTile>

      <StatTile title="CPU, all containers" figure={pct(overview.cpu_pct)} sub="of the NAS">
        <ul className="mt-2 grid gap-1 text-[11.5px]">
          {busiest.map((c) => (
            // On a phone the bar takes its own line under the name and the figure.
            <li
              key={c.name}
              className="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-x-2 gap-y-0.5 md:grid-cols-[minmax(0,4.5rem)_minmax(0,1fr)_2.25rem]"
            >
              <span className="truncate font-mono text-[11px] text-muted">{c.name}</span>
              <span className="order-last col-span-2 h-1 overflow-hidden rounded-full bg-raised md:order-none md:col-span-1" aria-hidden="true">
                <span
                  className="block h-full rounded-full bg-linear-to-r from-[#6f60ea] to-[#b4a9ff]"
                  style={{ width: `${Math.min(100, (c.cpu_pct! / Math.max(overview.cpu_pct, 0.1)) * 100)}%` }}
                />
              </span>
              <span className="text-right">{pct(c.cpu_pct!)}</span>
            </li>
          ))}
        </ul>
      </StatTile>

      <StatTile title="Memory, all containers" figure={formatBytes(overview.mem_bytes)} sub={memTotal ? `of ${formatBytes(memTotal)}` : undefined}>
        <p className="mt-2.5 flex h-2 gap-0.5 overflow-hidden rounded-full bg-raised" aria-hidden="true">
          {biggest.map((c, i) => (
            <i key={c.name} className="block h-full" style={{ width: `${(c.mem_bytes! / memTop) * 100}%`, backgroundColor: MEMORY_COLOURS[i] }} />
          ))}
          <i className="block h-full flex-1 bg-white/12" />
        </p>
        <ul className="mt-1.5 flex flex-wrap gap-x-2.5 gap-y-0.5 text-[11px] text-muted">
          {biggest.map((c, i) => (
            <li key={c.name} className="flex min-w-0 items-center gap-1">
              <i className="inline-block size-[7px] shrink-0 rounded-[2px]" style={{ backgroundColor: MEMORY_COLOURS[i] }} />
              <span className="truncate">{c.name}</span>
            </li>
          ))}
        </ul>
      </StatTile>

      <StatTile title="Updates, last 7 days" figure={recent} sub={recent === 1 ? 'image replaced' : 'images replaced'}>
        <p className="mt-2.5 flex items-end gap-1.5" aria-hidden="true">
          {days.map((d, i) => (
            <span key={i} className="grid justify-items-center gap-0.5 text-[10px] text-faint">
              <b
                className={cn('block w-2.5 rounded-[3px]', d.count ? 'bg-accent-line shadow-[0_0_6px_var(--color-accent-line)]' : 'bg-accent-line/25')}
                style={{ height: 6 + Math.min(d.count, 4) * 6 }}
              />
              {d.label}
            </span>
          ))}
        </p>
      </StatTile>
    </StatTiles>
  )
}
