import { DumpsCard } from '../components/backups/DumpsCard'
import { IncomingCard } from '../components/backups/IncomingCard'
import { MirrorCard } from '../components/backups/MirrorCard'
import { RestoreCheckCard } from '../components/backups/RestoreCheckCard'
import { LastNightCard } from '../components/backups/LastNightCard'
import { RunHistoryCard } from '../components/backups/RunHistoryCard'
import { StorageBoxCard } from '../components/backups/StorageBoxCard'
import { VolumesCard } from '../components/backups/VolumesCard'
import { Card } from '../components/ui/Card'
import { Loading, StaleNote, Unavailable } from '../components/ui/states'
import { PageHeader } from '../components/PageHeader'
import { Pill } from '../components/ui/Pill'
import { backupVerdict, VERDICT_PILL } from '../lib/backups'
import { cn } from '../lib/cn'
import type { BackupHistory, DatabaseDumps, GitHubMirror, IncomingBackups } from '../lib/types'
import { useApi } from '../lib/useApi'

export function BackupsPage() {
  const { data, error } = useApi<BackupHistory>('/api/backups', 300_000)
  const { data: mirror } = useApi<GitHubMirror>('/api/github-mirror', 300_000)
  const { data: dumps, reload: reloadDumps } = useApi<DatabaseDumps>('/api/database-dumps', 300_000)
  const { data: incoming } = useApi<IncomingBackups>('/api/incoming-backups', 300_000)
  const last = data?.runs[0]
  const recent = data?.runs.slice(0, 30) ?? []
  const now = new Date()
  const verdict = last && VERDICT_PILL[backupVerdict(last, now)]

  return (
    <>
      <PageHeader
        title="Backups"
        subtitle="Nightly rclone runs to the Hetzner storage box, encrypted"
        status={verdict && <Pill tone={verdict.tone}>{verdict.label}</Pill>}
      />

      {!data && (error ? <Unavailable what="Backup history" /> : <Loading />)}

      {data && !last && (
        <Card title="No runs recorded yet">
          <p className="text-muted">
            Run records start with the first backup after the updated backup.sh is pulled on the NAS. The Home page
            still shows the result of the last run until then.
          </p>
        </Card>
      )}

      {data && last && (
        <>
          <div className="mb-5">
            <LastNightCard last={last} history={data} dumps={dumps} now={now} />
          </div>

          <div className={cn('grid gap-5', data.storage_box && 'lg:grid-cols-[1fr_1.6fr]')}>
            {data.storage_box && <StorageBoxCard box={data.storage_box} />}
            {data.volumes.length > 0 && <VolumesCard volumes={data.volumes} />}
          </div>

          <RunHistoryCard runs={recent} volumes={data.volumes} />
          {data.stale && <StaleNote />}
        </>
      )}

      {dumps && (
        <div className="mt-5 grid items-start gap-5 lg:grid-cols-2">
          <DumpsCard dumps={dumps} />
          <RestoreCheckCard
            checks={dumps.restore_checks ?? []}
            lastVerified={dumps.last_verified ?? null}
            stale={dumps.stale}
            onFinished={reloadDumps}
          />
        </div>
      )}
      {incoming?.sources.map((source) => (
        <IncomingCard key={source.name} backup={source} stale={incoming.stale} now={now} />
      ))}
      {mirror?.enabled && <MirrorCard mirror={mirror} />}
    </>
  )
}
