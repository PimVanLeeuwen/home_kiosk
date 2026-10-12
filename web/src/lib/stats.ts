import { formatBytes, formatCount, formatPercent, formatRate } from './format'
import type { Stat } from './types'

const FORMAT: Record<Stat['unit'], (n: number) => string> = {
  count: formatCount,
  bytes: formatBytes,
  bytes_per_second: formatRate,
  percent: formatPercent,
}

/** "2 streaming · 812 movies": a one-line summary, optionally of the first `limit` stats. */
export function statsSummary(stats: Stat[], limit?: number): string {
  return stats
    .slice(0, limit)
    .map((s) => `${FORMAT[s.unit](s.value)} ${s.label.toLowerCase()}`)
    .join(' · ')
}

/** A stat as its figure and its word, for a chip: ["1.812", "movies"]. */
export function statParts(s: Stat): [string, string] {
  return [FORMAT[s.unit](s.value), s.label.toLowerCase()]
}
