import {
  formatBytes,
  formatCount,
  formatMbit,
  formatMoney,
  formatPercent,
  formatRate,
  formatSignedPct,
  formatWhen,
} from './format'

it('formats counts with Dutch grouping', () => {
  expect(formatCount(48213)).toBe('48.213')
  expect(formatCount(2)).toBe('2')
})

it('formats bytes like the kiosk', () => {
  expect(formatBytes(1_234_000_000_000)).toBe('1,2 TB')
  expect(formatBytes(912_000_000_000)).toBe('912 GB')
  expect(formatBytes(80_500_000)).toBe('81 MB')
})

it('formats transfer speeds', () => {
  expect(formatRate(5_000_000)).toBe('5,0 MB/s')
  expect(formatRate(250_000)).toBe('250 kB/s')
  expect(formatRate(0)).toBe('0 kB/s')
})

it('formats percentages', () => {
  expect(formatPercent(97.2)).toBe('97,2%')
  expect(formatPercent(100)).toBe('100,0%')
})

it('formats money, signed percentages and megabits', () => {
  expect(formatMoney(24490.42)).toBe('€\u00a024.490') // Intl keeps € and amount together
  expect(formatSignedPct(0.914)).toBe('+0,91%')
  expect(formatSignedPct(-1.1)).toBe('−1,10%')
  expect(formatSignedPct(0)).toBe('0,00%')
  expect(formatMbit(12.34)).toBe('12,3 Mbit/s')
})

it('formats when something happened relative to now', () => {
  const now = new Date(2026, 8, 30, 20, 0)
  expect(formatWhen(new Date(2026, 8, 30, 3, 31).toISOString(), now)).toBe('today 03:31')
  expect(formatWhen(new Date(2026, 8, 29, 3, 31).toISOString(), now)).toBe('yesterday 03:31')
  expect(formatWhen(new Date(2026, 8, 27, 3, 31).toISOString(), now)).toBe('Sun 27 Sept 03:31')
})
