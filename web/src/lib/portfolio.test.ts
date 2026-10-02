import { dayMove, holdingPath, parseHolding } from './portfolio'

describe('dayMove', () => {
  const base = { total_value: 1020, change: { day_abs: -7, day_pct: -0.7 } }

  it('sums the holdings, like the report and the bot', () => {
    const move = dayMove({ ...base, holdings: [{ day_abs: 30 }, { day_abs: -10 }] })
    expect(move.abs).toBe(20)
    expect(move.pct).toBeCloseTo(2) // 20 on 1000 before the move
  })

  it("falls back to Ghostfolio's figure without per-holding euros", () => {
    expect(dayMove({ ...base, holdings: [{ day_abs: 30 }, {}] })).toEqual({ abs: -7, pct: -0.7 })
    expect(dayMove({ ...base, holdings: [] })).toEqual({ abs: -7, pct: -0.7 })
  })
})

describe('holding addresses', () => {
  it('round-trip symbols with dots and carets', () => {
    for (const symbol of ['ASML.AS', '^GSPC', 'BRK-B']) {
      const param = new URL(`http://x${holdingPath({ data_source: 'YAHOO', symbol })}`).searchParams.get('h')
      expect(parseHolding(param)).toEqual({ dataSource: 'YAHOO', symbol })
    }
    expect(parseHolding('nonsense')).toBeNull()
    expect(parseHolding(null)).toBeNull()
  })
})
