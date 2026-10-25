import { briefingState, dnsState, laundryState, todayState } from './homeStates'
import type { Briefing, CalendarEvent, DnsStats, Laundry, Machine, Today } from './types'

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

describe('dnsState', () => {
  const dns = { answering: true, protection: true } as DnsStats

  it('is quiet while AdGuard blocks, and before the first answer', () => {
    expect(dnsState(dns)).toBe('quiet')
    expect(dnsState(undefined)).toBe('quiet')
  })

  it('is a warning when AdGuard does not answer or blocking is paused', () => {
    expect(dnsState({ ...dns, answering: false })).toBe('warn')
    expect(dnsState({ ...dns, protection: false })).toBe('warn')
  })
})

describe('briefingState', () => {
  const briefing = { date: '2026-10-29', until: new Date(2026, 9, 29, 9, 0).toISOString() } as Briefing

  it('shows the digest on its own day until 09:00', () => {
    expect(briefingState(briefing, new Date(2026, 9, 29, 6, 31))).toBe('live')
    expect(briefingState(briefing, new Date(2026, 9, 29, 9, 0))).toBe('hidden')
    expect(briefingState(briefing, new Date(2026, 9, 30, 7, 0))).toBe('hidden')
    expect(briefingState(undefined, new Date(2026, 9, 29, 7, 0))).toBe('hidden')
  })
})
