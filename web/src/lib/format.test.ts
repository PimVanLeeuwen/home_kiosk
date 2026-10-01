import {
  formatAgo,
  formatBytes,
  formatDuration,
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
  expect(formatBytes(2_400_000_000)).toBe('2,4 GB')
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

it('formats how long ago something happened', () => {
  const now = new Date('2026-10-01T12:00:00Z')
  const ago = (seconds: number) => formatAgo(new Date(now.getTime() - seconds * 1000).toISOString(), now)
  expect(ago(20)).toBe('just now')
  expect(ago(5 * 60)).toBe('5 min ago')
  expect(ago(3600)).toBe('1 hour ago')
  expect(ago(5 * 3600)).toBe('5 hours ago')
  expect(ago(86_400)).toBe('1 day ago')
  expect(ago(12 * 86_400)).toBe('12 days ago')
  expect(ago(90 * 86_400)).toBe('3 Jul 2026')
})

it('formats durations', () => {
  expect(formatDuration(45)).toBe('45 s')
  expect(formatDuration(241)).toBe('4 min')
  expect(formatDuration(4320)).toBe('1 h 12 min')
})
