import { Check } from 'lucide-react'
import { cn } from '../../lib/cn'
import type { DueReminder } from '../../lib/reminders'

interface Props {
  due: DueReminder[]
  /** Ticks a reminder off for today (or back on); without it the list only shows. */
  onToggle?: (reminder: DueReminder) => void
  busy?: boolean
}

/** Today's reminders, the ones with a time first, as on the Door panel; ticked-off ones struck through. */
export function TodayReminders({ due, onToggle, busy }: Props) {
  if (due.length === 0) return <p className="text-muted">Nothing to remember today.</p>
  return (
    <ul className="grid gap-1.5">
      {due.map((r) => (
        <li key={r.id} className={cn('flex items-center gap-3 rounded-[10px] px-2 py-1.5', !r.done && 'bg-raised/60')}>
          {onToggle ? (
            <button
              type="button"
              role="checkbox"
              aria-checked={r.done}
              aria-label={`${r.title} done`}
              disabled={busy}
              onClick={() => onToggle(r)}
              className={cn(
                'grid size-6 shrink-0 place-items-center rounded-full border',
                r.done ? 'border-up/60 bg-up/20 text-up' : 'border-line text-transparent hover:border-accent-line hover:text-faint',
              )}
            >
              <Check aria-hidden="true" className="size-3.5" />
            </button>
          ) : (
            <span aria-hidden="true" className={cn('size-2 shrink-0 rounded-full', r.done ? 'bg-up/60' : 'bg-accent-line')} />
          )}
          <span className={cn('min-w-0 flex-1 truncate text-title', r.done && 'text-faint line-through')}>{r.title}</span>
          <span className={cn('shrink-0 text-caption', r.at ? 'font-mono text-muted' : 'text-faint')}>{r.at ?? 'All day'}</span>
        </li>
      ))}
    </ul>
  )
}
