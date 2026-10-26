import { ROUTE, SESSION } from '../test/runningFixtures'
import { blockSeconds, clock, km, localDate, pace, paceColour, paceRange, project, sessionDay } from './running'

describe('the running helpers', () => {
  it('writes distances, paces and times', () => {
    expect([km(10400), km(132000, 0), pace(312), pace(255.4), clock(3248), clock(4930)]).toEqual([
      '10,4', '132', '5:12', '4:15', '54:08', '1:22:10',
    ])
  })

  it('fits a route into its box, north up', () => {
    const xy = project(ROUTE, 200, 100, 10)
    expect(Math.min(...xy.map((p) => p[0]))).toBeGreaterThanOrEqual(9.99)
    expect(Math.max(...xy.map((p) => p[0]))).toBeLessThanOrEqual(190.01)
    expect(Math.max(...xy.map((p) => p[1]))).toBeLessThanOrEqual(90.01)
    const north = ROUTE.reduce((a, b) => (b[0] > a[0] ? b : a))
    expect(xy[ROUTE.indexOf(north)][1]).toBeCloseTo(Math.min(...xy.map((p) => p[1])))
  })

  it('colours a pace against the run: cool when slow, white when fastest', () => {
    const [slowest, fastest] = paceRange(ROUTE)
    expect(slowest).toBeGreaterThan(fastest)
    expect(paceColour(slowest, slowest, fastest)).toBe('rgb(94 140 255)')
    expect(paceColour(fastest, slowest, fastest)).toBe('rgb(255 244 222)')
  })

  it('says when the next session is, and how long a block lasts', () => {
    expect(sessionDay(SESSION)).toBe('tomorrow')
    expect(sessionDay({ ...SESSION, date: localDate(new Date()) })).toBe('today')
    expect(SESSION.blocks.map(blockSeconds)).toEqual([720, 204, 90])
  })
})
