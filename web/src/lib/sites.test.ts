import { formatUptime, siteKey } from './sites'
import type { Site } from './types'

const site = (over: Partial<Site> = {}): Site => ({
  id: 1, name: 'AOC', group: 'Personal', up: true, down_since: null, ping_ms: 100, uptime_pct: 100,
  days: Array(30).fill('up'), ...over,
})

describe('sites', () => {
  it('shows uptime with two decimals, never rounding a bad month up to 100', () => {
    expect(formatUptime(99.81)).toBe('99,81%')
    expect(formatUptime(99.999)).toBe('99,99%')
    expect(formatUptime(100)).toBe('100,00%')
  })

  it('keys a site by its worst day', () => {
    expect(siteKey(site({ up: false }), 0)).toBe('var(--color-down)')
    expect(siteKey(site({ days: [...Array(29).fill('up'), 'down'] }), 0)).toBe('var(--color-down)')
    expect(siteKey(site({ days: ['blip', ...Array(29).fill('up')] }), 0)).toBe('var(--color-warn)')
    expect(siteKey(site(), 2)).toContain('var(--color-up) 73%')
  })
})
