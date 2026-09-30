import { statsSummary } from './stats'

it('summarises stats on one line', () => {
  expect(
    statsSummary([
      { label: 'Photos', value: 48213, unit: 'count' },
      { label: 'Storage', value: 912e9, unit: 'bytes' },
    ]),
  ).toBe('48.213 photos · 912 GB storage')
})

it('can limit the summary to the first stats', () => {
  const stats = [
    { label: 'Streaming', value: 2, unit: 'count' as const },
    { label: 'Movies', value: 812, unit: 'count' as const },
    { label: 'Series', value: 143, unit: 'count' as const },
  ]
  expect(statsSummary(stats, 2)).toBe('2 streaming · 812 movies')
})

it('formats speeds', () => {
  expect(
    statsSummary([
      { label: 'Active', value: 2, unit: 'count' },
      { label: 'Down', value: 5_000_000, unit: 'bytes_per_second' },
    ]),
  ).toBe('2 active · 5,0 MB/s down')
})
