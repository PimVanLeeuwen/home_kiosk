import { formatBytes, formatCount } from './format'

it('formats counts with Dutch grouping', () => {
  expect(formatCount(48213)).toBe('48.213')
  expect(formatCount(2)).toBe('2')
})

it('formats bytes like the kiosk', () => {
  expect(formatBytes(1_234_000_000_000)).toBe('1,2 TB')
  expect(formatBytes(912_000_000_000)).toBe('912 GB')
  expect(formatBytes(80_500_000)).toBe('81 MB')
})
