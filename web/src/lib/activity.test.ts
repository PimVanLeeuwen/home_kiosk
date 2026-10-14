import { activityStats, gridCells, monthLabels } from './activity'
import type { ContributionDay } from './types'

/** Days from Monday 29 June 2026 up to `until`, with counts by index. */
function days(until: string, count: (i: number) => number = () => 1): ContributionDay[] {
  const out: ContributionDay[] = []
  for (let d = new Date(2026, 5, 29), i = 0; ; d.setDate(d.getDate() + 1), i++) {
    const day = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
    out.push({ day, count: count(i), level: count(i) ? 2 : 0 })
    if (day === until) return out
  }
}

describe('activity', () => {
  it('fills the rest of this week with empty cells, sixteen columns in all', () => {
    const cells = gridCells(days('2026-10-14'))

    expect(cells).toHaveLength(112)
    expect(cells[107]?.day).toBe('2026-10-14')
    expect(cells.slice(108)).toEqual([null, null, null, null])
  })

  it('names a month over its first week, the first column only with room to spare', () => {
    const labels = monthLabels(gridCells(days('2026-10-14')))

    // 29 June opens the grid but July starts a week later: no room for "Jun".
    expect(labels.filter(Boolean)).toEqual(['Jul', 'Aug', 'Sept', 'Oct'].map((m) => expect.stringMatching(new RegExp(`^${m.slice(0, 3)}`))))
    expect(labels[0]).toBe('')
    expect(labels[1]).toMatch(/^Jul/)
  })

  it('counts this week, the streak and the busiest weekday', () => {
    // Wednesday 14 October: nothing yet today, but every day before had one.
    const list = days('2026-10-14', (i) => (i === 107 ? 0 : i % 7 === 1 ? 3 : 1))

    expect(activityStats(list)).toEqual({ thisWeek: 4, streak: 107, busiest: 'Tuesdays' })
  })

  it('has no streak or busiest day without contributions', () => {
    expect(activityStats(days('2026-07-05', () => 0))).toEqual({ thisWeek: 0, streak: 0, busiest: null })
    expect(activityStats([])).toEqual({ thisWeek: 0, streak: 0, busiest: null })
  })
})
