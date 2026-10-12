import { RESTORE_MAX_DAYS } from '../../lib/backups'
import { formatAgo } from '../../lib/format'
import type { DatabaseDumps } from '../../lib/types'

/** The monthly restore check in one line: verified (amber when old), or the last check failed. */
export function RestoreLine({ dumps, now, short }: { dumps: DatabaseDumps | undefined; now: Date; short?: boolean }) {
  const newest = dumps?.restore_checks?.[0]
  if (newest && !newest.ok)
    return <p className="text-[12.5px] text-down">{short ? 'Failed' : 'Last restore check failed'} {formatAgo(newest.finished, now)}</p>
  const verified = dumps?.last_verified
  if (!verified) return null
  const old = now.getTime() - new Date(verified).getTime() > RESTORE_MAX_DAYS * 86_400_000
  return (
    <p className={`text-[12.5px] ${old ? 'text-warn' : 'text-up'}`}>
      {short ? 'Verified' : 'Restore verified'} {formatAgo(verified, now)}
    </p>
  )
}
