import type { CalendarEvent, Today } from './types'
import { localDate } from './train'

/** The day ribbon runs from 07:00 to 23:00. */
export const DAY_FROM = 7
export const DAY_TO = 23

/** Whether Home shows the card: today's answer with at least one event. */
export function todayShows(today: Today | undefined, now: Date): today is Today {
  return !!today && today.date === localDate(now) && today.events.length + today.all_day.length > 0
}

export interface Focus {
  event: CalendarEvent
  /** In it now, or the next one to start. */
  now: boolean
  /** Minutes until it ends (now) or starts (next), rounded up. */
  minutes: number
}

/** The event under way, else the next one to start; null once the day is done. */
export function focusOf(events: CalendarEvent[], now: Date): Focus | null {
  const t = now.getTime()
  const at = (iso: string | null) => (iso ? new Date(iso).getTime() : 0)
  const current = events.find((e) => at(e.start) <= t && t < at(e.end ?? e.start))
  if (current) return { event: current, now: true, minutes: Math.ceil((at(current.end) - t) / 60_000) }
  const next = events.find((e) => at(e.start) > t)
  if (next) return { event: next, now: false, minutes: Math.ceil((at(next.start) - t) / 60_000) }
  return null
}

/** Where an hour sits on the ribbon, in percent; clamped to the ribbon's day. */
export function ribbonX(hours: number): number {
  return Math.min(100, Math.max(0, ((hours - DAY_FROM) / (DAY_TO - DAY_FROM)) * 100))
}

/** A moment as hours since local midnight (14:30 is 14,5). */
export function hoursOf(iso: string): number {
  const d = new Date(iso)
  return d.getHours() + d.getMinutes() / 60
}

/** Past: it has ended. */
export const isPast = (e: CalendarEvent, now: Date) => !!e.end && new Date(e.end).getTime() <= now.getTime()
