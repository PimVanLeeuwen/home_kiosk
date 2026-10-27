import { SHOARMA } from '../test/recipeFixtures'
import { COOK_KEY, cookViews, loadCook, localDay, phaseDone, saveCook, toggleTick } from './cookProgress'

const DAY = new Date(2026, 9, 27, 18, 30)

describe('cook progress', () => {
  beforeEach(() => localStorage.clear())

  it('pauses only between the last prep phase and the first cook phase', () => {
    expect(cookViews(SHOARMA)).toEqual([
      { kind: 'phase', phase: 0 },
      { kind: 'phase', phase: 1 },
      { kind: 'pause' },
      { kind: 'phase', phase: 2 },
      { kind: 'phase', phase: 3 },
    ])
    expect(cookViews({ ...SHOARMA, phases: SHOARMA.phases.slice(2) })).toHaveLength(2)
    expect(cookViews({ ...SHOARMA, phases: SHOARMA.phases.slice(0, 2) })).toHaveLength(2)
  })

  it('keeps ticks and place for the day and this version only', () => {
    let state = loadCook('kip', 'v1', 5, DAY)
    expect(state).toEqual({ day: '2026-10-27', version: 'v1', view: 0, ticks: [] })
    state = { ...toggleTick(state, '0.1'), view: 2 }
    saveCook('kip', state)

    expect(loadCook('kip', 'v1', 5, new Date(2026, 9, 27, 23, 59))).toEqual(state)
    expect(loadCook('kip', 'v1', 2, DAY).view).toBe(1)
    expect(loadCook('kip', 'v2', 5, DAY).ticks).toEqual([])
    expect(loadCook('kip', 'v1', 5, new Date(2026, 9, 28, 0, 1)).ticks).toEqual([])
  })

  it("forgets other days' recipes when saving", () => {
    saveCook('old', { ...loadCook('old', 'v1', 1, new Date(2026, 9, 26)), ticks: ['0.0'] })
    saveCook('kip', loadCook('kip', 'v1', 1, DAY))
    expect(Object.keys(JSON.parse(localStorage.getItem(COOK_KEY)!))).toEqual(['kip'])
  })

  it('survives storage that is not ours', () => {
    localStorage.setItem(COOK_KEY, '[1,2')
    expect(loadCook('kip', 'v1', 3, DAY).view).toBe(0)
  })

  it('ticks and unticks, and counts a phase', () => {
    const state = toggleTick(toggleTick(loadCook('kip', 'v1', 5, DAY), '0.0'), '0.1')
    expect(phaseDone(SHOARMA, state.ticks, 0)).toBe(2)
    expect(phaseDone(SHOARMA, toggleTick(state, '0.0').ticks, 0)).toBe(1)
    expect(localDay(new Date(2026, 0, 5))).toBe('2026-01-05')
  })
})
