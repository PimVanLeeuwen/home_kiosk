import { localDate, type RoutePoint, type RunningOverview, type Session } from '../lib/running'

/** A made-up loop in the North Sea, with the pace rising and falling. */
export const ROUTE: RoutePoint[] = Array.from({ length: 60 }, (_, i) => {
  const t = (i / 59) * Math.PI * 2
  return [52.5 + 0.01 * Math.sin(t), 3.5 + 0.016 * Math.cos(t), i ? 300 + 40 * Math.sin(i / 5) : null]
})

const day = (offset: number) => {
  const now = new Date()
  return localDate(new Date(now.getFullYear(), now.getMonth(), now.getDate() + offset))
}

export const SESSION: Session = {
  uid: 's1', date: day(1), time: null, name: 'Threshold Intervals', kind: 'Intervals', distance_m: 8300,
  estimate: '45m - 50m', estimate_s: 2850, race: false,
  steps: ['2km warm up at a conversational pace, 90s walking rest', '6 reps of:', '800m at 4:15/km, 90s walking rest'],
  blocks: [
    { kind: 'easy', metres: 2000, seconds: null, pace: null },
    { kind: 'work', metres: 800, seconds: null, pace: 255 },
    { kind: 'rest', metres: null, seconds: 90, pace: null },
  ],
}

export function overview(over: Partial<RunningOverview> = {}): RunningOverview {
  const monday = (() => {
    const now = new Date()
    return new Date(now.getFullYear(), now.getMonth(), now.getDate() - ((now.getDay() + 6) % 7))
  })()
  return {
    as_of: new Date().toISOString(), stale: false, has_plan: true,
    last: {
      id: 'r1', start: new Date(Date.now() - 26 * 3600e3).toISOString(), name: 'Outdoor Run', indoor: false,
      duration_s: 3248, distance_m: 10400, pace_s_per_km: 312, elevation_up_m: 12, avg_hr: 148, max_hr: 171,
      energy_kcal: 690, temperature_c: 9, bests: { '5k': 1421, '10k': 3002, half: null },
      route: ROUTE, splits: [], heart: [], session: 'Long Run',
    },
    week: Array.from({ length: 7 }, (_, i) => ({
      date: localDate(new Date(monday.getFullYear(), monday.getMonth(), monday.getDate() + i)),
      planned_m: i === 1 ? 8000 : 0, sessions: i === 1 ? ['Threshold Intervals'] : [],
      done_m: i === 0 ? 5200 : 0, routes: i === 0 ? [ROUTE.slice(0, 40)] : [],
    })),
    totals: { week_m: 5200, week_planned_m: 8000, last4_m: 132000, prev4_m: 120000, streak_weeks: 6, runs_this_year: 138, year_m: 1214000 },
    bests: { '5k': { seconds: 1421, start: '2026-09-12T07:00:00Z', id: 'a' }, '10k': null, half: null, longest: { metres: 21400, start: '2026-10-17T07:00:00Z', id: 'd' } },
    next: SESSION,
    today: { ran: false, session: null },
    race: null,
    ...over,
  }
}
