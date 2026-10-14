import type { ContributionDay } from './types'

export const WEEKS = 16
const WEEKDAYS = ['Mondays', 'Tuesdays', 'Wednesdays', 'Thursdays', 'Fridays', 'Saturdays', 'Sundays']
const month = new Intl.DateTimeFormat('en-GB', { month: 'short' })

/** A calendar date ("2026-10-14") as a local date, never shifted by time zones. */
function local(day: string): Date {
  const [y, m, d] = day.split('-').map(Number)
  return new Date(y, m - 1, d)
}

/** Monday 0 to Sunday 6. */
function weekday(day: string): number {
  return (local(day).getDay() + 6) % 7
}

/**
 * The grid's cells, a column per week from Monday: the days GitHub sent, then
 * `null` for the days still to come in this week.
 */
export function gridCells(days: ContributionDay[]): (ContributionDay | null)[] {
  const cells: (ContributionDay | null)[] = days.slice(-WEEKS * 7)
  while (cells.length % 7) cells.push(null)
  return cells
}

/**
 * A month name over the first week of each month, as on GitHub; the first
 * column's month only when the next one is at least three weeks away.
 */
export function monthLabels(cells: (ContributionDay | null)[]): string[] {
  const columns = cells.length / 7
  const months = Array.from({ length: columns }, (_, c) => {
    const first = cells[c * 7]
    return first ? local(first.day).getMonth() : -1
  })
  const labels = months.map((m, c) => (c > 0 && m !== months[c - 1] && m >= 0 ? month.format(local(cells[c * 7]!.day)) : ''))
  const next = labels.findIndex((l) => l)
  if (cells[0] && (next < 0 || next >= 3)) labels[0] = month.format(local(cells[0].day))
  return labels
}

export interface ActivityStats {
  thisWeek: number
  /** Days in a row with a contribution, up to today (or yesterday, while today has none yet). */
  streak: number
  /** The weekday with the most contributions, as "Tuesdays"; null without any. */
  busiest: string | null
}

export function activityStats(days: ContributionDay[]): ActivityStats {
  let monday = days.length - 1
  while (monday > 0 && weekday(days[monday].day) !== 0) monday -= 1
  const thisWeek = days.slice(Math.max(0, monday)).reduce((n, d) => n + d.count, 0)

  let end = days.length - 1
  if (end >= 0 && days[end].count === 0) end -= 1
  let streak = 0
  while (end - streak >= 0 && days[end - streak].count > 0) streak += 1

  const perDay = Array<number>(7).fill(0)
  for (const d of days) perDay[weekday(d.day)] += d.count
  const top = Math.max(...perDay)
  return { thisWeek, streak, busiest: top > 0 ? WEEKDAYS[perDay.indexOf(top)] : null }
}
