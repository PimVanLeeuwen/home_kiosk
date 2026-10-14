import { focusOf, hoursOf, isPast, ribbonX, todayShows } from './today'
import type { CalendarEvent, Today } from './types'

const at = (h: number, m = 0) => new Date(2026, 9, 14, h, m).toISOString()
const ev = (s: [number, number], e: [number, number], title: string): CalendarEvent => ({
  calendar_id: 'w', calendar: 'Work', color: '#5aa9ff', title, start: at(...s), end: at(...e), all_day: false,
})
const EVENTS = [ev([9, 30], [10, 0], 'Standup'), ev([12, 30], [13, 30], 'Lunch')]
const today = (over: Partial<Today> = {}): Today => ({ as_of: at(9), stale: false, date: '2026-10-14', events: EVENTS, all_day: [], errors: {}, ...over })

describe('today', () => {
  it("shows today's answer with events, never another day's or an empty one", () => {
    const now = new Date(2026, 9, 14, 9, 0)
    expect(todayShows(today(), now)).toBe(true)
    expect(todayShows(today({ date: '2026-10-13' }), now)).toBe(false)
    expect(todayShows(today({ events: [] }), now)).toBe(false)
    expect(todayShows(today({ events: [], all_day: [{ ...EVENTS[0], all_day: true }] }), now)).toBe(true)
    expect(todayShows(undefined, now)).toBe(false)
  })

  it('focuses on the event under way, else the next, else nothing', () => {
    expect(focusOf(EVENTS, new Date(2026, 9, 14, 9, 6))).toMatchObject({ now: false, minutes: 24, event: { title: 'Standup' } })
    expect(focusOf(EVENTS, new Date(2026, 9, 14, 12, 54))).toMatchObject({ now: true, minutes: 36, event: { title: 'Lunch' } })
    expect(focusOf(EVENTS, new Date(2026, 9, 14, 14, 0))).toBeNull()
  })

  it('places hours on the 07:00 to 23:00 ribbon', () => {
    expect(ribbonX(7)).toBe(0)
    expect(ribbonX(15)).toBe(50)
    expect(ribbonX(23.5)).toBe(100)
    expect(ribbonX(5)).toBe(0)
    expect(hoursOf(at(14, 30))).toBe(14.5)
  })

  it('knows when an event is past', () => {
    expect(isPast(EVENTS[0], new Date(2026, 9, 14, 10, 0))).toBe(true)
    expect(isPast(EVENTS[1], new Date(2026, 9, 14, 10, 0))).toBe(false)
  })
})
