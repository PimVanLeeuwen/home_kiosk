import { Check, Pencil } from 'lucide-react'
import { cn } from '../../lib/cn'
import { dueText, type Todo } from '../../lib/todos'
import { iconButtonClass } from '../ui/buttonStyles'
import { Tag } from '../ui/Tag'

interface Props {
  todos: Todo[]
  today: string
  /** Ticks a todo off (removes it); without it the list only shows. */
  onTick?: (todo: Todo) => void
  onEdit?: (todo: Todo) => void
  /** Show each todo's note under its title (the page; the card leaves them out). */
  notes?: boolean
  /** Show this many, then "and N more". */
  limit?: number
  busy?: boolean
}

/** Open todos in the hub's order: High first, then by due date; overdue in red, today in violet. */
export function TodoList({ todos, today, onTick, onEdit, notes, limit, busy }: Props) {
  if (todos.length === 0) return <p className="text-muted">Nothing to do. Enjoy it.</p>
  const shown = limit ? todos.slice(0, limit) : todos
  const more = todos.length - shown.length
  return (
    <>
      <ul className="grid grid-cols-1 gap-1.5">
        {shown.map((t) => (
          <li key={t.id} className="flex items-start gap-3 rounded-control bg-raised/60 px-2 py-1.5">
            {onTick ? (
              <button
                type="button"
                role="checkbox"
                aria-checked={false}
                aria-label={`${t.title} done`}
                disabled={busy}
                onClick={() => onTick(t)}
                className="mt-0.5 grid size-6 shrink-0 place-items-center rounded-full border border-line-strong text-transparent hover:border-accent-line hover:text-faint disabled:opacity-50"
              >
                <Check aria-hidden="true" className="size-3.5" />
              </button>
            ) : (
              <span aria-hidden="true" className="mt-2 size-2 shrink-0 rounded-full border border-line-strong" />
            )}
            <div className="min-w-0 flex-1 py-0.5">
              <p className="flex items-center gap-2">
                <span className="min-w-0 truncate text-title">{t.title}</span>
                {t.high && (
                  <Tag tone="warn" size="micro" caps>
                    High
                  </Tag>
                )}
              </p>
              {notes && t.note && <p className="text-small whitespace-pre-line text-muted">{t.note}</p>}
            </div>
            {t.due && (
              <span
                className={cn(
                  'shrink-0 py-0.5 text-small',
                  t.state === 'overdue' ? 'font-medium text-down' : t.state === 'today' ? 'font-medium text-accent-fg' : 'text-muted',
                )}
              >
                {dueText(t.due, today)}
              </span>
            )}
            {onEdit && (
              <button type="button" aria-label={`Change ${t.title}`} className={iconButtonClass} onClick={() => onEdit(t)}>
                <Pencil aria-hidden="true" className="size-4" />
              </button>
            )}
          </li>
        ))}
      </ul>
      {more > 0 && <p className="mt-2 text-small text-faint">and {more} more</p>}
    </>
  )
}
