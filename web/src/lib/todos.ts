/**
 * Todos (plan.md M37): what you want done, kept until it is. The hub (app/todos.py) keeps
 * them in order (High, then due date, then oldest) and marks each overdue or due today;
 * this words it.
 */

import { localDay } from './reminders'

export interface TodoDraft {
  title: string
  note: string | null
  /** YYYY-MM-DD, or null. */
  due: string | null
  high: boolean
}

export interface Todo extends TodoDraft {
  id: number
  created: string
  state: 'overdue' | 'today' | null
}

/** `/api/todos`; a tick's answer also carries the todo it removed, for Undo. */
export interface Todos {
  as_of: string
  stale: boolean
  today: string
  open: number
  overdue: number
  due_today: number
  todos: Todo[]
  removed?: Todo
}

export const BLANK_TODO: TodoDraft = { title: '', note: null, due: null, high: false }

/** How many a card or a short list shows before "and N more". */
export const CARD_TODOS = 5

const dayLine = new Intl.DateTimeFormat('en-GB', { weekday: 'short', day: 'numeric', month: 'short' })

/** "3 days late", "Yesterday", "Today", "Tomorrow", "Wed 12 Nov"; "" without a date. */
export function dueText(due: string | null, today: string): string {
  if (!due) return ''
  const days = Math.round((localDay(due).getTime() - localDay(today).getTime()) / 86_400_000)
  if (days === 0) return 'Today'
  if (days === 1) return 'Tomorrow'
  if (days === -1) return 'Yesterday'
  if (days < 0) return `${-days} days late`
  return dayLine.format(localDay(due))
}

/** The page's header word: "3 open, 1 overdue", "Nothing open". */
export function openText(data: Pick<Todos, 'open' | 'overdue' | 'due_today'>): string {
  if (!data.open) return 'Nothing open'
  const extra = data.overdue ? `, ${data.overdue} overdue` : data.due_today ? `, ${data.due_today} today` : ''
  return `${data.open} open${extra}`
}
