import { POOL_FULL_PCT } from '../../lib/attention'
import { formatBytes, formatRunway } from '../../lib/format'
import { shortRunway } from '../../lib/nasHealth'
import type { Pool } from '../../lib/types'
import { Card } from '../ui/Card'
import { ArcGauge } from '../ui/ArcGauge'

/** Every pool on a dial, fullest first, with its free space and runway, and all of them together below. */
export function StorageCard({ pools }: { pools: Pool[] }) {
  const used = pools.reduce((sum, p) => sum + p.used_bytes, 0)
  const total = pools.reduce((sum, p) => sum + p.total_bytes, 0)
  const pct = total ? (used / total) * 100 : 0
  return (
    <Card
      title="Storage"
      actions={pools.length > 1 && <span className="text-label font-semibold tracking-[0.08em] text-faint uppercase">Fullest first</span>}
    >
      {pools.length === 0 ? (
        <p className="text-muted">No storage pools reported.</p>
      ) : (
        <>
          <ul className="grid gap-3.5 sm:grid-cols-2 xl:grid-cols-3">
            {/* Pools arrive fullest first. */}
            {pools.map((pool) => (
              <li
                key={pool.name}
                className="grid grid-cols-[130px_minmax(0,1fr)] items-center gap-2.5 rounded-[12px] border border-glass-line bg-glass p-3 text-left sm:grid-cols-1 sm:text-center"
              >
                <ArcGauge pct={pool.used_pct} alertAt={POOL_FULL_PCT} label={pool.name} className="mx-auto w-full sm:w-[82%] sm:max-w-[200px]" />
                <div className="min-w-0">
                  <p className="font-mono text-caption font-semibold">{pool.name}</p>
                  <p className="text-caption text-muted">
                    {formatBytes(pool.used_bytes)} of {formatBytes(pool.total_bytes)}
                  </p>
                  <p className="text-caption text-muted">{formatBytes(pool.free_bytes)} free</p>
                  <p className={shortRunway(pool) ? 'text-caption text-warn' : 'text-caption text-faint'}>{formatRunway(pool.projection_months)}</p>
                </div>
              </li>
            ))}
          </ul>
          {pools.length > 1 && (
            <div className="mt-4 flex items-center gap-3 border-t border-line-soft pt-3 text-small">
              <span className="text-label font-semibold tracking-[0.06em] text-faint uppercase">All pools</span>
              <span
                role="meter"
                aria-label="All pools"
                aria-valuenow={Math.round(pct)}
                aria-valuemin={0}
                aria-valuemax={100}
                className="h-[5px] flex-1 overflow-hidden rounded-full bg-raised"
              >
                <span className="block h-full rounded-full bg-linear-to-r from-[var(--color-accent)] to-[var(--color-accent-fg)]" style={{ width: `${pct}%` }} />
              </span>
              <span className="whitespace-nowrap">
                {formatBytes(used)} of {formatBytes(total)} used
              </span>
            </div>
          )}
        </>
      )}
    </Card>
  )
}
