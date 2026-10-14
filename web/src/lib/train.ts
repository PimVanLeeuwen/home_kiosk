import type { Tone } from '../components/ui/tones'
import type { Train, TrainRun } from './types'

/** A local date as YYYY-MM-DD, as the collector writes `date`. */
export function localDate(d: Date): string {
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
}

/**
 * Whether Home shows the card: this morning's train until it has left, or
 * tomorrow's in the evening when it has a problem. A payload for another day
 * (yesterday's, kept overnight) never shows.
 */
export function trainShows(train: Train | undefined, now: Date): train is Train {
  if (!train || !train.watching) return false
  const day = new Date(now)
  if (train.mode === 'evening') day.setDate(day.getDate() + 1)
  else if (train.mode !== 'morning') return false
  return train.date === localDate(day)
}

/** The run that still leaves: the train itself, or the next direct one when it does not run. */
export function followed(train: Train): TrainRun | null {
  const run = train.train
  if (run && run.status !== 'cancelled' && run.status !== 'not_found') return run
  return train.next_direct
}

/** Minutes until a run leaves (its actual time when known), rounded up as the NS app does; never below zero. */
export function minutesToGo(run: TrainRun, now: Date): number {
  const at = new Date(run.actual_departure ?? run.planned_departure).getTime()
  return Math.max(0, Math.ceil((at - now.getTime()) / 60_000))
}

export interface TrainStatus {
  word: string
  tone: Tone
}

/** The large line: how the train is doing, or, in the evening, what is wrong tomorrow. */
export function trainStatus(train: Train): TrainStatus {
  const run = train.train
  if (!run || run.status === 'not_found') return { word: "Not in NS's planner", tone: 'down' }
  if (run.status === 'cancelled') return { word: 'Cancelled', tone: 'down' }
  const skipped = run.stops.slice(1).filter((s) => s.cancelled)
  if (train.mode === 'evening') {
    if (skipped.length) return { word: `Skips ${skipped.map((s) => s.name).join(', ')}`, tone: 'warn' }
    return { word: 'Works on the route', tone: 'warn' }
  }
  if (run.status === 'late') return { word: `${run.delay_minutes} min late`, tone: 'warn' }
  if (skipped.length) return { word: `Skips ${skipped.map((s) => s.name).join(', ')}`, tone: 'warn' }
  return { word: 'On time', tone: 'up' }
}
