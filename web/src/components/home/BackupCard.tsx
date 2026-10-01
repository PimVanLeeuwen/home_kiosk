import { cn } from '../../lib/cn'
import { formatBytes, formatDuration, formatWhen } from '../../lib/format'
import type { BackupHistory, Nas } from '../../lib/types'
import { useApi } from '../../lib/useApi'
import { Card, Loading, Unavailable } from './Card'

const LABEL = { ok: 'Succeeded', fail: 'Failed', unknown: 'Unknown' } as const
const TONE = { ok: 'text-up', fail: 'text-down', unknown: 'text-muted' } as const

/**
 * The latest nightly run: per volume from the run history when it exists,
 * else just the result from backup.sh's status marker (in /api/nas).
 */
export function BackupCard({ nas, error }: { nas: Nas | undefined; error: Error | undefined }) {
  const history = useApi<BackupHistory>('/api/backups', 300_000)
  const last = history.data?.runs[0]

  return (
    <Card title="Backups" link={{ to: '/backups', label: 'History' }}>
      {last ? (
        <>
          <p className="text-[13px] text-muted">Last nightly run to Hetzner</p>
          <p className="mt-1 text-[22px] font-semibold">
            <span className={last.ok ? 'text-up' : 'text-down'}>{last.ok ? 'Succeeded' : 'Failed'}</span>
            <span className="ml-2 text-[15px] font-normal text-muted">{formatWhen(last.finished)}</span>
          </p>
          <ul className="mt-3 space-y-1.5 text-[13px]">
            {last.volumes.map((v) => (
              <li key={v.name} className="flex justify-between gap-3">
                <span className="text-muted">{v.name}</span>
                <span className={cn(!v.ok && 'text-down')}>
                  {v.ok ? 'OK' : 'Failed'} · {formatDuration(v.seconds)}
                  {v.ok && v.bytes != null && ` · ${formatBytes(v.bytes)}`}
                </span>
              </li>
            ))}
          </ul>
          {history.data?.next_due && (
            <p className="mt-4 text-[12.5px] text-faint">Next run due {formatWhen(history.data.next_due)}</p>
          )}
        </>
      ) : (
        <>
          {!nas && (error ? <Unavailable what="Backup status" /> : <Loading />)}
          {nas && (
            <>
              <p className="text-[13px] text-muted">Last nightly run to Hetzner</p>
              <p className="mt-1 text-[22px] font-semibold">
                <span className={TONE[nas.backup.status]}>{LABEL[nas.backup.status]}</span>
                {nas.backup.at && (
                  <span className="ml-2 text-[15px] font-normal text-muted">{formatWhen(nas.backup.at)}</span>
                )}
              </p>
            </>
          )}
        </>
      )}
    </Card>
  )
}
