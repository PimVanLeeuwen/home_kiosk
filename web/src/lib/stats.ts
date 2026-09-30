import { formatBytes, formatCount } from './format'
import type { Stat } from './types'

/** "2 streaming · 812 movies": a one-line summary, optionally of the first `limit` stats. */
export function statsSummary(stats: Stat[], limit?: number): string {
  return stats
    .slice(0, limit)
    .map((s) =>
      s.unit === 'bytes'
        ? `${formatBytes(s.value)} ${s.label.toLowerCase()}`
        : `${formatCount(s.value)} ${s.label.toLowerCase()}`,
    )
    .join(' · ')
}
