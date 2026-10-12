import { BACKUP_MAX_AGE_HOURS } from '../../lib/attention'
import { formatAgo, formatBytes, formatDuration, formatWhen } from '../../lib/format'
import type { BackupHistory, BackupRun, DatabaseDumps, Nas } from '../../lib/types'
import { useApi } from '../../lib/useApi'
import { BarStrip } from '../ui/BarStrip'
import { FlowLine } from '../ui/FlowLine'
import { Pill } from '../ui/Pill'
import { Seal } from '../ui/Seal'
import type { Tone } from '../ui/tones'
import { Card, Loading, Unavailable } from './Card'

const NIGHTS = 30
/** A night this much slower than usual stands out in amber. */
const SLOW_FACTOR = 1.3
/** The backup_missing rule's default: a restore check older than this needs a new one. */
const RESTORE_MAX_DAYS = 45

const seconds = (run: BackupRun) => (new Date(run.finished).getTime() - new Date(run.started).getTime()) / 1000

function median(values: number[]): number {
  const sorted = [...values].sort((a, b) => a - b)
  return sorted[Math.floor(sorted.length / 2)] ?? 0
}

/** The last nights oldest first, failed ones red and slow ones amber. */
function nights(runs: BackupRun[]) {
  const shown = runs.slice(0, NIGHTS).reverse()
  const minutes = shown.map((r) => seconds(r) / 60)
  const usual = median(minutes)
  const marks: Record<number, Tone> = {}
  shown.forEach((r, i) => {
    if (!r.ok) marks[i] = 'down'
    else if (usual > 0 && minutes[i] > usual * SLOW_FACTOR) marks[i] = 'warn'
  })
  // Name the newest failure if there is one, else the first slow night.
  const failedAt = Object.keys(marks).map(Number).filter((i) => marks[i] === 'down').pop()
  const slowAt = Object.keys(marks).map(Number).find((i) => marks[i] === 'warn')
  const markAt = failedAt ?? slowAt
  return { minutes, marks, markAt, markLabel: failedAt != null ? 'failed' : slowAt != null ? 'slow' : undefined }
}

function RestoreLine({ dumps, now }: { dumps: DatabaseDumps | undefined; now: Date }) {
  const newest = dumps?.restore_checks?.[0]
  if (newest && !newest.ok) return <p className="text-[12.5px] text-down">Last restore check failed {formatAgo(newest.finished, now)}</p>
  const verified = dumps?.last_verified
  if (!verified) return null
  const old = now.getTime() - new Date(verified).getTime() > RESTORE_MAX_DAYS * 86_400_000
  return <p className={`text-[12.5px] ${old ? 'text-warn' : 'text-up'}`}>Restore verified {formatAgo(verified, now)}</p>
}

/**
 * The latest nightly run with the nights before it: per volume from the run
 * history when it exists, else just the result from backup.sh's status marker
 * (in /api/nas).
 */
export function BackupCard({ nas, error }: { nas: Nas | undefined; error: Error | undefined }) {
  const history = useApi<BackupHistory>('/api/backups', 300_000)
  const dumps = useApi<DatabaseDumps>('/api/database-dumps', 300_000)
  const runs = history.data?.runs ?? []
  const last = runs[0]
  const now = new Date()
  const overdue = !!last && now.getTime() - new Date(last.finished).getTime() > BACKUP_MAX_AGE_HOURS * 3_600_000
  const pill = !last ? null : !last.ok ? (
    <Pill tone="down">Failed</Pill>
  ) : overdue ? (
    <Pill tone="warn">Overdue</Pill>
  ) : (
    <Pill tone="up">All safe</Pill>
  )

  return (
    <Card title="Backups" link={{ to: '/backups', label: 'History' }} actions={pill}>
      {last ? (
        <LastRun last={last} runs={runs} history={history.data!} dumps={dumps.data} now={now} />
      ) : (
        <>
          {!nas && (error ? <Unavailable what="Backup status" /> : <Loading />)}
          {nas && (
            <div className="flex items-center gap-4">
              {nas.backup.status !== 'unknown' && (
                <Seal ok={nas.backup.status === 'ok'} label={nas.backup.status === 'ok' ? 'Backup succeeded' : 'Backup failed'} />
              )}
              <div>
                <p className="text-[13px] text-muted">Last nightly run to Hetzner</p>
                <p className="mt-0.5 text-[22px] font-semibold">
                  <span className={nas.backup.status === 'ok' ? 'text-up' : nas.backup.status === 'fail' ? 'text-down' : 'text-muted'}>
                    {nas.backup.status === 'ok' ? 'Succeeded' : nas.backup.status === 'fail' ? 'Failed' : 'Unknown'}
                  </span>
                  {nas.backup.at && <span className="ml-2 text-[14px] font-normal text-muted">{formatWhen(nas.backup.at)}</span>}
                </p>
              </div>
            </div>
          )}
        </>
      )}
    </Card>
  )
}

interface LastRunProps {
  last: BackupRun
  runs: BackupRun[]
  history: BackupHistory
  dumps: DatabaseDumps | undefined
  now: Date
}

function LastRun({ last, runs, history, dumps, now }: LastRunProps) {
  const bytes = last.volumes.reduce((sum, v) => sum + (v.ok && v.bytes != null ? v.bytes : 0), 0)
  const failed = last.volumes.filter((v) => !v.ok)
  const strip = nights(runs)
  const n = strip.minutes.length
  return (
    <>
      <div className="flex items-center gap-4">
        <Seal ok={last.ok} label={last.ok ? 'Backup succeeded' : 'Backup failed'} />
        <div className="min-w-0">
          <p className="text-[22px] font-semibold">
            <span className={last.ok ? 'text-up' : 'text-down'}>{last.ok ? 'Succeeded' : 'Failed'}</span>
            <span className="ml-2 text-[14px] font-normal text-muted">{formatWhen(last.finished)}</span>
          </p>
          <p className="text-[12.5px] text-muted">
            {last.volumes.length} {last.volumes.length === 1 ? 'volume' : 'volumes'} · {formatDuration(seconds(last))}
            {bytes > 0 && ` · ${formatBytes(bytes)}`}
          </p>
          <RestoreLine dumps={dumps} now={now} />
        </div>
      </div>
      {failed.length > 0 && (
        <ul className="mt-3 space-y-1 text-[13px]">
          {failed.map((v) => (
            <li key={v.name} className="flex justify-between gap-3">
              <span className="text-muted">{v.name}</span>
              <span className="text-down">Failed · {formatDuration(v.seconds)}</span>
            </li>
          ))}
        </ul>
      )}
      <div className="my-3.5">
        <FlowLine from="NAS" to="Hetzner · encrypted" ok={last.ok} />
      </div>
      <BarStrip
        values={strip.minutes}
        label={`Backup durations, last ${n} ${n === 1 ? 'night' : 'nights'}`}
        marks={strip.marks}
        markLabel={strip.markLabel}
        markAt={strip.markAt}
        start={`${n} ${n === 1 ? 'night' : 'nights'}`}
        end="last night"
      />
      {history.next_due && <p className="mt-2.5 text-[12.5px] text-faint">Next run due {formatWhen(history.next_due)}</p>}
    </>
  )
}
