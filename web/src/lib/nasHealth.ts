import { POOL_FULL_PCT } from './attention'
import type { Nas, Pool } from './types'

/** CPU temperature: amber from here, red (and worth a look) from the hot mark. */
export const WARM_CPU_C = 70
export const HOT_CPU_C = 80

/** A runway shorter than this is worth a look. */
export const SHORT_RUNWAY_MONTHS = 6

/** A disk this warm is shown in amber. */
export const WARM_DISK_C = 50

export const shortRunway = (pool: Pick<Pool, 'projection_months'>) =>
  pool.projection_months != null && pool.projection_months < SHORT_RUNWAY_MONTHS

/** The NAS card's and page's "Needs a look": a full pool, a disk with SMART trouble or a hot CPU. */
export function nasNeedsLook(nas: Nas): boolean {
  return (
    nas.storage.pools.some((p) => p.used_pct >= POOL_FULL_PCT) ||
    nas.disks.some((d) => d.smart !== 'ok') ||
    (nas.cpu_temp_c ?? 0) >= HOT_CPU_C
  )
}
