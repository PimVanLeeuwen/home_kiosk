import { rainSummary } from './rain'

// Local times, so the expected clock times hold in any time zone.
const at = (minute: number) => new Date(2026, 9, 9, 15, minute).toISOString()
const series = (...mm: number[]) => mm.map((v, i) => ({ at: at(i * 5), mm_per_hour: v }))

it('sums up the next two hours of rain', () => {
  expect(rainSummary(series(0, 0, 0.05, 0))).toBe('Dry for the next 2 hours')
  expect(rainSummary(series(0, 0, 0.4, 2.3, 0))).toBe('Rain from 15:10, up to 2,3 mm/h')
  expect(rainSummary(series(1.2, 0.6, 0, 0))).toBe('Rain now, up to 1,2 mm/h; dry from 15:10')
  expect(rainSummary(series(0.5, 0.8))).toBe('Rain for the next 2 hours, up to 0,8 mm/h')
  expect(rainSummary([])).toBe('No rain forecast available')
})
