/** Something that needs a look (Today's attention rows come from the hub's open incidents instead). */
export interface Attention {
  level: 'warn' | 'down'
  text: string
}

/** A backup older than this counts as missed; it runs nightly. */
export const BACKUP_MAX_AGE_HOURS = 26
export const POOL_FULL_PCT = 90
