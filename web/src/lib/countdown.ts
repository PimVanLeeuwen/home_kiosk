import type { CountdownEvent } from './pieceTypes'

const DAY_MS = 86_400_000

/** Whole days from today (local) to a YYYY-MM-DD date; 0 on the day itself. */
export function daysUntil(date: string, now: Date): number {
  const [y, m, d] = date.split('-').map(Number)
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate())
  return Math.round((new Date(y, m - 1, d).getTime() - today.getTime()) / DAY_MS)
}

/** The countdowns still ahead (today included), nearest first. */
export const ahead = (events: CountdownEvent[] | undefined, now: Date): CountdownEvent[] =>
  (events ?? []).filter((e) => daysUntil(e.date, now) >= 0)

export const daysWord = (n: number) => `${n} day${n === 1 ? '' : 's'}`

// The tunnel as the Now panel paints it (app/paint_countdown.py), laid flatter for a card.
export const W = 400
export const H = 230
export const CORE = { x: 200, y: 78 }
const NEAREST = 250
const MOST = 40
export const SPARKS = 10

export interface Ring {
  key: number
  cx: number
  cy: number
  rx: number
  ry: number
  /** How much white is mixed in: the far rings white-hot. */
  white: number
  opacity: number
  width: number
}

/** One ring per day left (at most 40), closing in on the core in perspective; the tunnel bends down to you. */
export function tunnel(days: number): Ring[] {
  const n = Math.max(1, Math.min(MOST, days))
  return Array.from({ length: n }, (_, k) => {
    const i = n - k
    const depth = i / n
    const r = NEAREST / (1 + 11 * depth ** 1.1)
    return {
      key: i,
      cx: CORE.x,
      cy: CORE.y + (1 - depth) ** 1.6 * 70,
      rx: r,
      ry: r * 0.58,
      white: Math.round(75 * depth ** 0.8),
      opacity: i === 1 ? 1 : 0.35 + 0.65 * depth ** 0.5,
      width: 0.8 + 2.4 * (1 - depth) ** 2,
    }
  })
}
