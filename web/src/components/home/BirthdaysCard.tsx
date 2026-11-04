import { cn } from '../../lib/cn'
import type { Birthday, Birthdays } from '../../lib/types'
import { Card } from '../ui/Card'
import { Loading, StaleNote, Unavailable } from '../ui/states'

const weekday = new Intl.DateTimeFormat('en-GB', { weekday: 'short' })

function when(b: Birthday): string {
  if (b.days === 0) return 'Today'
  if (b.days === 1) return 'Tomorrow'
  return `in ${b.days} days`
}

const dayOf = (b: Birthday) => {
  const [y, m, d] = b.date.split('-').map(Number)
  return new Date(y, m - 1, d)
}

/** The contacts' birthdays today and in the next 7 days (plan.md M32), as on the Door panel. */
export function BirthdaysCard({ data, error }: { data: Birthdays | undefined; error?: Error }) {
  return (
    <Card title="Birthdays">
      {!data && error && <Unavailable what="Birthdays" plural detail="The hub reads them from your iCloud contacts." />}
      {!data && !error && <Loading what="birthdays" />}
      {data && data.birthdays.length === 0 && <p className="text-muted">No birthdays this week.</p>}
      {data && data.birthdays.length > 0 && (
        <ul className="grid gap-2">
          {data.birthdays.map((b) => {
            const today = b.days === 0
            const date = dayOf(b)
            return (
              <li
                key={`${b.name}-${b.date}`}
                className={cn('flex items-center gap-3 rounded-[10px] px-2 py-1.5', today && 'bg-accent-soft ring-1 ring-accent-line/40')}
              >
                <span
                  aria-hidden="true"
                  className={cn(
                    'flex w-10 shrink-0 flex-col items-center rounded-[8px] border py-1 leading-none',
                    today ? 'border-accent-line/60 text-accent-fg' : 'border-line text-muted',
                  )}
                >
                  <span className="text-micro uppercase">{weekday.format(date)}</span>
                  <span className="mt-0.5 text-title font-semibold text-fg">{date.getDate()}</span>
                </span>
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-title font-medium">{b.name}</span>
                  {b.turns !== null && <span className="block text-caption text-muted">turns {b.turns}</span>}
                </span>
                <span className={cn('shrink-0 text-caption', today ? 'font-semibold text-accent-fg' : 'text-faint')}>{when(b)}</span>
              </li>
            )
          })}
        </ul>
      )}
      {data?.stale && <StaleNote />}
    </Card>
  )
}
