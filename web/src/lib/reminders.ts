/**
 * Reminders (plan.md M32): what you set in the hub to remember on a day, for the Door
 * panel, the Home card and an ntfy message. The hub (app/reminders.py) works out when
 * each one falls; this words it.
 */

export type RepeatKind = 'none' | 'every' | 'weekly' | 'monthly' | 'yearly'
export type Notify = 'none' | 'at' | 'hour' | 'evening'

export interface Repeat {
  kind: RepeatKind
  every: number
  unit: 'days' | 'weeks'
  /** Monday 0, for weekly. */
  weekdays: number[]
  /** The day of the month, or the last one, for monthly. */
  day: number | 'last'
}

export interface ReminderDraft {
  title: string
  /** The first day, YYYY-MM-DD. */
  start: string
  /** "07:30", or null for the whole day. */
  at: string | null
  repeat: Repeat
  notify: Notify
}

export interface Reminder extends ReminderDraft {
  id: number
  /** The next day it falls, from today on; null when it never will again. */
  next: string | null
}

export interface DueReminder {
  id: number
  title: string
  at: string | null
  done: boolean
}

/** `/api/reminders`. */
export interface Reminders {
  as_of: string
  stale: boolean
  today: string
  /** Today's, the ones with a time first. */
  due: DueReminder[]
  reminders: Reminder[]
}

export const NO_REPEAT: Repeat = { kind: 'none', every: 1, unit: 'days', weekdays: [], day: 1 }

export const WEEKDAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']

const dayMonth = new Intl.DateTimeFormat('en-GB', { day: 'numeric', month: 'short' })
const dayLine = new Intl.DateTimeFormat('en-GB', { weekday: 'short', day: 'numeric', month: 'short' })

/** A YYYY-MM-DD date as a local Date. */
export function localDay(iso: string): Date {
  const [y, m, d] = iso.split('-').map(Number)
  return new Date(y, m - 1, d)
}

export function isoDay(d: Date): string {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

function ordinal(n: number): string {
  const tens = n % 100
  const suffix = tens >= 11 && tens <= 13 ? 'th' : ({ 1: 'st', 2: 'nd', 3: 'rd' } as Record<number, string>)[n % 10] ?? 'th'
  return `${n}${suffix}`
}

function list(words: string[]): string {
  return words.length < 2 ? words.join('') : `${words.slice(0, -1).join(', ')} and ${words[words.length - 1]}`
}

/** "Once", "Every 2 weeks", "Every Mon and Thu", "Monthly on the last day", "Every year on 4 Nov". */
export function repeatText(r: Pick<ReminderDraft, 'start' | 'repeat'>): string {
  const rep = r.repeat
  switch (rep.kind) {
    case 'none':
      return 'Once'
    case 'every':
      if (rep.every === 1) return rep.unit === 'weeks' ? 'Every week' : 'Every day'
      return `Every ${rep.every} ${rep.unit}`
    case 'weekly':
      return `Every ${list(rep.weekdays.map((d) => WEEKDAYS[d]))}`
    case 'monthly':
      return rep.day === 'last' ? 'Monthly on the last day' : `Monthly on the ${ordinal(rep.day)}`
    case 'yearly':
      return `Every year on ${dayMonth.format(localDay(r.start))}`
  }
}

/** What the ntfy message does, in a few words. */
export function notifyText(r: Pick<ReminderDraft, 'at' | 'notify'>): string {
  switch (r.notify) {
    case 'none':
      return 'No message'
    case 'at':
      return `Message at ${r.at ?? '08:00'}`
    case 'hour':
      return 'Message an hour before'
    case 'evening':
      return 'Message the evening before'
  }
}

/** "Today", "Tomorrow", "Wed 12 Nov", or "No more" for one that has passed. */
export function nextText(next: string | null, today: string): string {
  if (!next) return 'No more'
  const days = Math.round((localDay(next).getTime() - localDay(today).getTime()) / 86_400_000)
  if (days === 0) return 'Today'
  if (days === 1) return 'Tomorrow'
  return dayLine.format(localDay(next))
}
