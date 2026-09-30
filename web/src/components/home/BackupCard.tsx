import { formatWhen } from '../../lib/format'
import type { Nas } from '../../lib/types'
import { Card, Loading, Unavailable } from './Card'

const LABEL = { ok: 'Succeeded', fail: 'Failed', unknown: 'Unknown' } as const
const TONE = { ok: 'text-up', fail: 'text-down', unknown: 'text-muted' } as const

/** The latest nightly run. Per-volume history arrives with milestone M4. */
export function BackupCard({ nas, error }: { nas: Nas | undefined; error: Error | undefined }) {
  return (
    <Card title="Backups" link={{ to: '/backups', label: 'History' }}>
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
          <p className="mt-4 text-[12.5px] text-faint">Run history per volume arrives with milestone M4.</p>
        </>
      )}
    </Card>
  )
}
