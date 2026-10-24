import { formatAgo } from '../../lib/format'
import type { OutsideService } from '../../lib/types'

/** Which status pages could not be read, and how old their last answer is. */
export function ReadNotes({ services }: { services: OutsideService[] }) {
  const unread = services.filter((s) => s.stale)
  if (unread.length === 0) return null
  return (
    <ul className="mt-3 grid gap-0.5 text-caption text-warn">
      {unread.map((s) => (
        <li key={s.key}>
          {s.name}: {s.error ?? 'the status page could not be read'}
          {s.state === 'unknown' ? '.' : `; showing its answer from ${formatAgo(s.as_of)}.`}
        </li>
      ))}
    </ul>
  )
}
