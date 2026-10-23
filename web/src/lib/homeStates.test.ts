import { laundryState, todayState } from './homeStates'
import type { CalendarEvent, Laundry, Machine, Today } from './types'

const at = (h: number, m = 0) => new Date(2026, 9, 23, h, m)
const event = (from: number, to: number): CalendarEvent => ({
  calendar_id: 'w', calendar: 'Work', color: '#5aa9ff', title: 'Stand-up',
  start: at(from).toISOString(), end: at(to).toISOString(), all_day: false,
})
const today = (events: CalendarEvent[]): Today => ({
  as_of: at(7).toISOString(), stale: false, date: '2026-10-23', events, all_day: [], errors: {},
})

describe('todayState', () => {
  it('is now during an event, live within the hour before one, quiet before that', () => {
    const day = today([event(10, 11)])
    expect(todayState(day, at(10, 30))).toBe('now')
    expect(todayState(day, at(9, 15))).toBe('live')
    expect(todayState(day, at(8, 30))).toBe('quiet')
  })
})

describe('laundryState', () => {
  const machine = (state: Machine['state']): Machine => ({
    id: 'w', name: 'Washing machine', kind: 'washer', state, online: true, door_open: false, error: null,
    done_at: null, program: null, remaining_minutes: null, total_minutes: null, ready_at: null,
  })
  const laundry = (state: Machine['state'], showing = true): Laundry => ({
    as_of: at(10).toISOString(), stale: false, showing, machines: [machine(state)],
  })

  it('is hidden when the hub hides it, a warning on an error, live otherwise', () => {
    expect(laundryState(laundry('idle', false))).toBe('hidden')
    expect(laundryState(laundry('error'))).toBe('warn')
    expect(laundryState(laundry('done'))).toBe('live')
  })
})
