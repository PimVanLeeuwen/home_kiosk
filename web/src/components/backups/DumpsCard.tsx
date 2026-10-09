import { Card, StaleNote } from '../home/Card'
import { cn } from '../../lib/cn'
import { formatBytes, formatWhen } from '../../lib/format'
import type { DatabaseDumps, DumpedDatabase } from '../../lib/types'

function Status({ db }: { db: DumpedDatabase }) {
  if (db.ok == null) return <span className="text-muted">Not run yet</span>
  return (
    <>
      <span className={cn('font-semibold', db.ok ? 'text-up' : 'text-down')}>{db.ok ? 'Succeeded' : 'Failed'}</span>
      {db.ok && db.bytes != null && <span className="text-muted"> · {formatBytes(db.bytes)}</span>}
    </>
  )
}

/** The nightly database dumps on the Backups page: one line per database. */
export function DumpsCard({ dumps }: { dumps: DatabaseDumps }) {
  const recent = dumps.runs.slice(0, 30)
  const succeeded = recent.filter((r) => r.ok).length

  return (
    <Card title="Database dumps" className="mt-5">
      <p className="mb-3 text-[13px] text-muted">
        Consistent copies of the live databases, made before the nightly backup takes them to Hetzner: a{' '}
        <span className="font-mono text-[12px]">pg_dump</span> per Postgres database at 02:30 into{' '}
        <span className="font-mono text-[12px]">/volume3/backups/databases</span>, and the hub's own database at 02:45.
      </p>
      <ul className="divide-y divide-line-soft text-[13.5px]">
        {dumps.databases.map((db) => (
          <li key={db.name} className="py-2.5 first:pt-0 last:pb-0">
            <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-0.5">
              <span>
                <span className="font-semibold">{db.label}</span>{' '}
                <span className="font-mono text-[12px] text-faint">{db.kind === 'sqlite' ? 'SQLite' : 'pg_dump'}</span>
              </span>
              <span>
                <Status db={db} />
              </span>
            </div>
            {db.ok != null && (
              <p className="text-[12.5px] text-muted">
                {db.at && <>Last attempt {formatWhen(db.at)} · </>}
                Last success {db.last_success ? formatWhen(db.last_success) : 'never recorded'}
              </p>
            )}
            {db.ok === false && db.error && (
              <p className="mt-1.5 rounded-lg border border-down/40 bg-down/10 px-3 py-2 font-mono text-[12px] break-words text-fg">
                {db.error}
              </p>
            )}
          </li>
        ))}
      </ul>
      <p className="mt-3 text-[12.5px] text-muted">
        {recent.length === 0 ? (
          <>
            No dump run recorded yet. The dumps run from root's crontab on the NAS (see the nas-docker README, Database
            dumps).
          </>
        ) : (
          <>
            Host job: <span className={cn(succeeded < recent.length && 'text-warn')}>{succeeded} of {recent.length}</span>{' '}
            recent runs succeeded
          </>
        )}
      </p>
      {dumps.stale && <StaleNote />}
    </Card>
  )
}
