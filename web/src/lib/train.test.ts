import { followed, localDate, minutesToGo, trainShows, trainStatus } from './train'
import type { Train, TrainRun } from './types'

const at = (h: number, m: number, day = 14) => new Date(2026, 9, day, h, m).toISOString()

function run(over: Partial<TrainRun> = {}): TrainRun {
  return {
    name: 'IC 3522', status: 'on_time', planned_departure: at(7, 16), actual_departure: at(7, 16),
    delay_minutes: 0, planned_track: '6', actual_track: '6',
    stops: [
      { name: 'Leiden Centraal', planned: at(7, 16), actual: at(7, 16), track: '6', cancelled: false },
      { name: 'Rotterdam Centraal', planned: at(8, 28), actual: at(8, 28), track: '2', cancelled: false },
    ],
    ...over,
  }
}

function train(over: Partial<Train> = {}): Train {
  return {
    as_of: at(6, 40), stale: false, date: '2026-10-14', route: 'Leiden Centraal to Rotterdam Centraal',
    departure: '07:16', mode: 'morning', watching: true, departed: false, train: run(), next_direct: null,
    disruptions: [], ...over,
  }
}

describe('train', () => {
  it('writes local dates as the collector does', () => {
    expect(localDate(new Date(2026, 9, 4, 23, 59))).toBe('2026-10-04')
  })

  it("shows this morning's train, and tomorrow's in the evening, never another day's", () => {
    const morning = new Date(2026, 9, 14, 6, 42)
    const evening = new Date(2026, 9, 13, 20, 5)

    expect(trainShows(train(), morning)).toBe(true)
    expect(trainShows(train({ mode: 'evening' }), evening)).toBe(true)
    expect(trainShows(train(), new Date(2026, 9, 15, 6, 42))).toBe(false)
    expect(trainShows(train({ watching: false }), morning)).toBe(false)
    expect(trainShows(train({ mode: 'idle' }), morning)).toBe(false)
    expect(trainShows(undefined, morning)).toBe(false)
  })

  it('counts the minutes to go up, from the actual time', () => {
    expect(minutesToGo(run(), new Date(2026, 9, 14, 6, 42))).toBe(34)
    expect(minutesToGo(run({ actual_departure: at(7, 22) }), new Date(2026, 9, 14, 6, 42, 30))).toBe(40)
    expect(minutesToGo(run(), new Date(2026, 9, 14, 7, 30))).toBe(0)
  })

  it('follows the next direct train when it does not run', () => {
    const next = run({ planned_departure: at(7, 46) })

    expect(followed(train())?.planned_departure).toBe(at(7, 16))
    expect(followed(train({ train: run({ status: 'cancelled' }), next_direct: next }))).toBe(next)
    expect(followed(train({ train: null, next_direct: null }))).toBeNull()
  })

  it('words the status by state, and the evening by what is wrong', () => {
    expect(trainStatus(train())).toEqual({ word: 'On time', tone: 'up' })
    expect(trainStatus(train({ train: run({ status: 'late', delay_minutes: 6 }) }))).toEqual({ word: '6 min late', tone: 'warn' })
    expect(trainStatus(train({ train: run({ status: 'cancelled' }) }))).toEqual({ word: 'Cancelled', tone: 'down' })
    expect(trainStatus(train({ train: null }))).toEqual({ word: "Not in NS's planner", tone: 'down' })
    expect(trainStatus(train({ mode: 'evening' })).word).toBe('Works on the route')
    const skipping = run({ stops: [run().stops[0], { ...run().stops[1], cancelled: true }] })
    expect(trainStatus(train({ mode: 'evening', train: skipping })).word).toBe('Skips Rotterdam Centraal')
  })
})
