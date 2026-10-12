import { cn } from '../../lib/cn'
import { formatWhen } from '../../lib/format'
import type { ContainerUpdate } from '../../lib/types'
import { Card } from '../home/Card'

const SHOWN = 25
const shortId = (id: string) => id.replace(/^sha256:/, '').slice(0, 12)

/** Image updates as a timeline, newest first and lit: the container, its image, and the old and new image ids. */
export function UpdatesCard({ updates }: { updates: ContainerUpdate[] }) {
  return (
    <Card
      title="Image updates"
      className="mt-5"
      actions={<span className="text-[11px] font-semibold tracking-[0.08em] text-faint uppercase">Watchtower and Dockge</span>}
    >
      {updates.length === 0 ? (
        <p className="text-muted">
          No updates seen yet. The hub notices when Watchtower or Dockge recreates a container from a new image.
        </p>
      ) : (
        <ol className="ml-1.5 border-l border-line pl-4">
          {updates.slice(0, SHOWN).map((u, i) => (
            <li
              key={`${u.at}-${u.name}`}
              className="relative grid grid-cols-[auto_minmax(0,1fr)] items-baseline gap-x-3 gap-y-0.5 py-1.5 text-[13px] md:grid-cols-[9.5rem_9.5rem_minmax(0,1fr)_auto]"
            >
              <span
                aria-hidden="true"
                className={cn(
                  'absolute top-[0.85em] -left-[20.5px] size-[7px] rounded-full',
                  i === 0 ? 'bg-accent-line shadow-[0_0_7px_var(--color-accent-line)]' : 'bg-faint',
                )}
              />
              <span className="text-faint">{formatWhen(u.at)}</span>
              <span className="truncate font-mono">{u.name}</span>
              <span className="col-span-2 truncate text-muted md:col-span-1">{u.image}</span>
              <span className="col-span-2 font-mono text-[11px] whitespace-nowrap text-muted md:col-span-1">
                <span className="rounded-[5px] border border-glass-line bg-glass px-1.5 py-px">{shortId(u.old_image_id)}</span>
                <span aria-label="replaced by"> → </span>
                <span className="rounded-[5px] border border-accent-line/40 bg-glass px-1.5 py-px text-accent-fg">
                  {shortId(u.new_image_id)}
                </span>
              </span>
            </li>
          ))}
        </ol>
      )}
    </Card>
  )
}
