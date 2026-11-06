import { WEEKS } from '../test/portfolioFixtures'
import { formatPrice, pickAnother, pointTime, weekView } from './stockWeek'

const [NVDA, ASML] = WEEKS.stocks

describe('weekView', () => {
  it('measures the week from the close before it, with its days in the exchange zone', () => {
    const view = weekView(NVDA)!
    expect(view.change).toBeCloseTo(10)
    expect(view.base).toBe(100)
    expect(view.days).toEqual([{ at: 0, label: 'Fri' }, { at: 2, label: 'Mon' }])
    expect([view.high, view.low]).toEqual([3, 1])
    expect(weekView(ASML)!.change).toBeCloseTo(-7.5)
  })

  it('needs two points and falls back to the first without a previous close', () => {
    expect(weekView({ ...NVDA, points: NVDA.points.slice(0, 1) })).toBeNull()
    expect(weekView({ ...NVDA, previous_close: null })!.change).toBeCloseTo(((110 - 101) / 101) * 100)
  })

  it('tells a point in the exchange time, and copes with an unknown zone', () => {
    expect(pointTime(NVDA, 0)).toBe('Fri 09:30')
    expect(weekView({ ...NVDA, zone: 'Nowhere/Else' })!.days).toHaveLength(2)
  })
})

describe('formatPrice', () => {
  it('writes each currency its own way', () => {
    expect(formatPrice(181.6, 'USD')).toMatch(/^US\$\s181,60$/)
    expect(formatPrice(1295, 'EUR')).toMatch(/^€\s1\.295,00$/)
    expect(formatPrice(1234.5, 'GBp')).toBe('1.234,5p')
    expect(formatPrice(9.5, null)).toBe('9,50')
    expect(formatPrice(9.5, 'NOPE')).toBe('9,50 NOPE')
  })
})

describe('pickAnother', () => {
  it('never picks the one before, and each other one as often', () => {
    expect([0, 0.34, 0.5, 0.99].map((r) => pickAnother(3, 1, () => r))).toEqual([0, 0, 2, 2])
    expect(pickAnother(3, 1, () => 0.2)).toBe(0)
    expect(pickAnother(1, 0, () => 0.9)).toBe(0)
    expect(pickAnother(4, null, () => 0.5)).toBe(2)
  })
})
