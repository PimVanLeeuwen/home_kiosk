/** Runs and Runna's plan (`/api/runs/overview`, plan.md M28): types and the drawing helpers. */

const LOCALE = 'nl-NL'

/** A route point: latitude, longitude and the pace since the point before (seconds per km). */
export type RoutePoint = [number, number, number | null]

export interface Block {
  kind: 'easy' | 'work' | 'rest'
  metres: number | null
  seconds: number | null
  /** Seconds per km, for work at a set pace. */
  pace: number | null
}

export interface Session {
  uid: string
  date: string
  time: string | null
  name: string
  kind: string | null
  distance_m: number | null
  estimate: string | null
  estimate_s: number | null
  steps: string[]
  race: boolean
  blocks: Block[]
}

export interface RunSummary {
  id: string
  start: string
  name: string
  indoor: boolean
  duration_s: number
  distance_m: number | null
  pace_s_per_km: number | null
  elevation_up_m: number | null
  avg_hr: number | null
  max_hr: number | null
  energy_kcal: number | null
  temperature_c: number | null
  bests: Record<'5k' | '10k' | 'half', number | null>
}

export interface LastRun extends RunSummary {
  route: RoutePoint[]
  splits: { km: number; seconds: number; metres: number }[]
  heart: [number, number][]
  /** Runna's session of that day, when there was one. */
  session: string | null
  /** When its area's streets were fetched, for the map under the route; null until then. */
  streets_at?: string | null
}

export interface WeekDay {
  date: string
  planned_m: number
  sessions: string[]
  done_m: number
  routes: RoutePoint[][]
}

export interface Best {
  seconds?: number
  metres?: number
  start: string
  id: string
}

export interface RunningOverview {
  as_of: string
  stale: boolean
  has_plan: boolean
  last: LastRun | null
  week: WeekDay[]
  totals: {
    week_m: number
    week_planned_m: number
    last4_m: number
    prev4_m: number
    streak_weeks: number
    runs_this_year: number
    year_m: number
  }
  bests: Record<'5k' | '10k' | 'half' | 'longest', Best | null>
  next: Session | null
  today: { ran: boolean; session: Session | null }
  race: Session | null
  /** When home's streets were fetched, for "Your streets"; null until asked for in Settings. */
  streets_at?: string | null
  /** This year's runs outside the home area, which "Your streets" leaves out. */
  runs_elsewhere?: number
}

/** "10,4" (km), with one decimal. */
export const km = (metres: number, digits = 1) =>
  new Intl.NumberFormat(LOCALE, { minimumFractionDigits: digits, maximumFractionDigits: digits }).format(metres / 1000)

/** "5:12", minutes and seconds per km. */
export function pace(secondsPerKm: number): string {
  const s = Math.round(secondsPerKm)
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`
}

/** "54:08", or "1:02:10" past the hour. */
export function clock(seconds: number): string {
  const s = Math.round(seconds)
  const h = Math.floor(s / 3600)
  const m = Math.floor((s % 3600) / 60)
  const rest = String(s % 60).padStart(2, '0')
  return h ? `${h}:${String(m).padStart(2, '0')}:${rest}` : `${m}:${rest}`
}

/** The route fitted into a box of `w` by `h` with `pad` round it, north up, as x and y. */
export function project(points: RoutePoint[], w: number, h: number, pad: number): [number, number][] {
  if (!points.length) return []
  const mid = (Math.min(...points.map((p) => p[0])) + Math.max(...points.map((p) => p[0]))) / 2
  const squeeze = Math.cos((mid * Math.PI) / 180) // a degree of longitude is shorter up north
  const xs = points.map((p) => p[1] * squeeze)
  const ys = points.map((p) => -p[0])
  const [x0, x1, y0, y1] = [Math.min(...xs), Math.max(...xs), Math.min(...ys), Math.max(...ys)]
  const scale = Math.min((w - 2 * pad) / Math.max(x1 - x0, 1e-9), (h - 2 * pad) / Math.max(y1 - y0, 1e-9))
  const dx = (w - (x1 - x0) * scale) / 2
  const dy = (h - (y1 - y0) * scale) / 2
  return xs.map((x, i) => [dx + (x - x0) * scale, dy + (ys[i] - y0) * scale])
}

const mixHex = (a: number[], b: number[], t: number) => a.map((v, i) => Math.round(v + (b[i] - v) * t))
const COOL = [94, 140, 255]
const WARM = [255, 168, 92]
const HOT = [255, 244, 222]

/** A pace as colour against the run's own range: cool blue when slow, amber, white when fastest. */
export function paceColour(p: number | null, slowest: number, fastest: number): string {
  if (p == null || slowest <= fastest) return `rgb(${WARM.join(' ')})`
  const t = Math.max(0, Math.min(1, (slowest - p) / (slowest - fastest)))
  const c = t < 0.7 ? mixHex(COOL, WARM, t / 0.7) : mixHex(WARM, HOT, (t - 0.7) / 0.3)
  return `rgb(${c.join(' ')})`
}

/** The run's pace range, leaving out the stops and the sprints at the ends (5th to 95th). */
export function paceRange(points: RoutePoint[]): [number, number] {
  const paces = points.map((p) => p[2]).filter((p): p is number => p != null && p > 120 && p < 1200).sort((a, b) => a - b)
  if (!paces.length) return [360, 300]
  return [paces[Math.floor(paces.length * 0.95)] ?? paces.at(-1)!, paces[Math.floor(paces.length * 0.05)] ?? paces[0]]
}

/** Seconds per km assumed for easy running when the plan gives no pace. */
export const EASY_PACE = 360

/** How long each block lasts, for the next session's shape. */
export const blockSeconds = (b: Block) => b.seconds ?? ((b.metres ?? 0) / 1000) * (b.pace ?? EASY_PACE)

const weekday = new Intl.DateTimeFormat('en-GB', { weekday: 'long' })

/** A date as YYYY-MM-DD in local time, as the hub's days are. */
export const localDate = (d: Date) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`

/** "today", "tomorrow" or the weekday, for the next session. */
export function sessionDay(s: Session, now = new Date()): string {
  const today = localDate(now)
  const tomorrow = localDate(new Date(now.getFullYear(), now.getMonth(), now.getDate() + 1))
  if (s.date === today) return 'today'
  if (s.date === tomorrow) return 'tomorrow'
  const [y, m, d] = s.date.split('-').map(Number)
  return weekday.format(new Date(y, m - 1, d))
}
