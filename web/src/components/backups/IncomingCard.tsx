import { Card } from '../ui/Card'
import { Pill } from '../ui/Pill'
import { StaleNote } from '../ui/states'
import { RunDots } from '../ui/RunDots'
import { incomingLate } from '../../lib/backups'
import { cn } from '../../lib/cn'
import { formatAgo, formatBytes, formatCount, formatWhen } from '../../lib/format'
import type { IncomingBackup } from '../../lib/types'

function Tile({ value, label }: { value: string; label: string }) {
  return (
    <div className="min-w-0 rounded-control border border-glass-line bg-glass px-3 py-2">
      <p className="text-heading leading-tight font-semibold">{value}</p>
      <p className="truncate text-caption text-muted">{label}</p>
    </div>
  )
}

/** A backup another machine pushes to this NAS, on the Backups page: when it last arrived and the recent nights. */
export function IncomingCard({ backup, stale, now }: { backup: IncomingBackup; stale: boolean; now: Date }) {
  const late = incomingLate(backup, now)
  const nights = backup.nights.map((n) => ({ ok: n.ok }))
  const received = nights.filter((n) => n.ok).length

  return (
    <Card
      title={backup.label}
      note="Incoming"
      actions={<Pill tone={late ? 'down' : 'up'}>{late ? 'Late' : 'On time'}</Pill>}
      className="mt-5"
    >
      <div className="grid items-start gap-4 lg:grid-cols-[minmax(0,1.2fr)_minmax(0,1fr)] lg:gap-6">
        <div className="min-w-0">
          {backup.present && backup.bytes !== null && (
            <div className="flex flex-wrap gap-2">
              <Tile value={formatBytes(backup.bytes)} label="on the NAS" />
              <Tile value={formatCount(backup.files ?? 0)} label="files" />
            </div>
          )}
          <p className="mt-3 text-caption text-muted">
            A backup another NAS sends here{backup.at ? ` every night at ${backup.at}` : ''}, over Tailscale. It writes
            no report, so it counts as arrived when something in its folder changes.
          </p>
        </div>
        <div className="min-w-0">
          <dl className="grid grid-cols-[auto_minmax(0,1fr)] gap-x-4 gap-y-1.5 text-small">
            <dt className="text-muted">Last arrived</dt>
            <dd>
              {backup.last_change ? (
                <>
                  <span className={cn('font-semibold', late ? 'text-down' : 'text-up')}>
                    {formatWhen(backup.last_change, now)}
                  </span>{' '}
                  <span className="text-muted">{formatAgo(backup.last_change, now)}</span>
                </>
              ) : (
                <span className="font-semibold text-down">Never</span>
              )}
            </dd>
            <dt className="text-muted">Alert after</dt>
            <dd>
              {backup.max_days} {backup.max_days === 1 ? 'day' : 'days'} without one
            </dd>
            {nights.length > 0 && (
              <>
                <dt className="text-muted">Nights, last {nights.length}</dt>
                <dd className="flex flex-wrap items-center gap-x-2.5 gap-y-1">
                  <span className={cn(received < nights.length && 'text-warn')}>
                    {received} of {nights.length}
                  </span>
                  <RunDots runs={nights} label={`Backups from ${backup.label}, last ${nights.length} nights, oldest first`} />
                </dd>
              </>
            )}
          </dl>
          {!backup.present && (
            <p className="mt-3 rounded-control border border-down/40 bg-down/10 px-3 py-2 font-mono text-caption break-words text-fg">
              The folder cannot be read{backup.error ? `: ${backup.error}` : ''}
            </p>
          )}
        </div>
      </div>
      {stale && <StaleNote />}
    </Card>
  )
}
