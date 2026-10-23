import { Card } from '../ui/Card'
import { StaleNote } from '../ui/states'
import { cn } from '../../lib/cn'
import { formatBytes, formatWhen } from '../../lib/format'
import type { DatabaseDumps, DumpedDatabase } from '../../lib/types'
import { GlowDot } from '../ui/GlowDot'
import { RunDots } from '../ui/RunDots'

function Status({ db }: { db: DumpedDatabase }) {
  if (db.ok == null) return <span className="text-muted">Not run yet</span>
  return (
    <>
      <span className={cn('font-semibold', db.ok ? 'text-up' : 'text-down')}>{db.ok ? 'Succeeded' : 'Failed'}</span>
      {db.ok && db.bytes != null && <span className="text-muted"> · {formatBytes(db.bytes)}</span>}
    </>
  )
}

/** The nightly database dumps on the Backups page: a glass row per database and the host job's recent runs. */
export function DumpsCard({ dumps }: { dumps: DatabaseDumps }) {
  const recent = dumps.runs.slice(0, 30)
  const succeeded = recent.filter((r) => r.ok).length

  return (
    <Card
      title="Database dumps"
      actions={<span className="text-[11px] font-semibold tracking-[0.08em] text-faint uppercase">02:30 · 02:45</span>}
    >
      <p className="mb-3 text-[12.5px] text-muted">
        Consistent copies of the live databases, made before the nightly backup takes them to Hetzner: a{' '}
        <span className="font-mono text-[12px]">pg_dump</span> per Postgres database at 02:30 into{' '}
        <span className="font-mono text-[12px]">/volume3/backups/databases</span>, and the hub's own database at 02:45.
      </p>
      <ul className="grid gap-2 text-[13px]">
        {dumps.databases.map((db) => {
          const failed = db.ok === false
          return (
            <li
              key={db.name}
              className={cn(
                'grid grid-cols-[12px_minmax(0,1fr)_auto] items-center gap-x-2.5 gap-y-1 rounded-[10px] border px-3 py-2.5',
                failed ? 'border-down/40 bg-linear-to-br from-down/12 to-down/[0.03]' : 'border-glass-line bg-glass',
              )}
            >
              <GlowDot tone={db.ok == null ? 'muted' : db.ok ? 'up' : 'down'} halo={failed} className="size-[7px]" />
              <span className="min-w-0">
                <span className="font-semibold">{db.label}</span>
                <span
                  className={cn(
                    'ml-1.5 rounded-[6px] px-1.5 text-[10.5px] font-semibold tracking-[0.04em]',
                    db.kind === 'sqlite' ? 'bg-[#8cc4ff]/14 text-[#8cc4ff]' : 'bg-accent/18 text-accent-fg',
                  )}
                >
                  {db.kind === 'sqlite' ? 'SQLite' : 'pg_dump'}
                </span>
              </span>
              <span className="text-right">
                <Status db={db} />
              </span>
              {db.ok != null && (
                <p className="col-start-2 col-end-4 text-[12px] text-muted">
                  {db.at && <>Last attempt {formatWhen(db.at)} · </>}
                  Last success {db.last_success ? formatWhen(db.last_success) : 'never recorded'}
                </p>
              )}
              {failed && db.error && (
                <p className="col-start-2 col-end-4 rounded-lg border border-down/40 bg-down/10 px-2.5 py-1.5 font-mono text-[11.5px] break-words text-fg">
                  {db.error}
                </p>
              )}
            </li>
          )
        })}
      </ul>
      <div className="mt-3 border-t border-line-soft pt-2.5 text-[12.5px] text-muted">
        {recent.length === 0 ? (
          <p>
            No dump run recorded yet. The dumps run from root's crontab on the NAS (see the nas-docker README, Database
            dumps).
          </p>
        ) : (
          <p className="flex flex-wrap items-center gap-x-3 gap-y-1.5">
            <span>
              Host job: <span className={cn(succeeded < recent.length && 'text-warn')}>{succeeded} of {recent.length}</span>{' '}
              recent runs succeeded
            </span>
            <RunDots runs={recent} label={`The last ${recent.length} dump runs, oldest first`} />
          </p>
        )}
      </div>
      {dumps.stale && <StaleNote />}
    </Card>
  )
}
