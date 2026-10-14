import type { Site, SiteDay } from './types'

/** Day colours on the rings and in the list. */
export const DAY_COLOUR: Record<Exclude<SiteDay, 'none'>, string> = {
  up: 'var(--color-up)',
  blip: 'var(--color-warn)',
  down: 'var(--color-down)',
}

/** The site's colour key in the list: its worst day, else its ring's green. */
export function siteKey(site: Site, index: number): string {
  if (site.up === false || site.days.includes('down')) return DAY_COLOUR.down
  if (site.days.includes('blip')) return DAY_COLOUR.blip
  return `color-mix(in srgb, var(--color-up) ${85 - index * 6}%, transparent)`
}

const twoDecimals = new Intl.NumberFormat('nl-NL', { minimumFractionDigits: 2, maximumFractionDigits: 2 })

/**
 * Uptime with two decimals, "99,81%": one decimal would round 99,97 up to a
 * misleading 100,0%. Never rounds up to 100 for a site that was down.
 */
export function formatUptime(pct: number): string {
  const floored = Math.floor(pct * 100) / 100
  return `${twoDecimals.format(floored)}%`
}
