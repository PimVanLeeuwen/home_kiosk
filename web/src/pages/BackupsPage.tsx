import { DumpsCard } from '../components/backups/DumpsCard'
import { MirrorCard } from '../components/backups/MirrorCard'
import { RestoreCheckCard } from '../components/backups/RestoreCheckCard'
import { RunBars } from '../components/backups/RunBars'
import { StorageBoxCard } from '../components/backups/StorageBoxCard'
import { Card, Loading, StaleNote, Unavailable } from '../components/home/Card'
import { PageHeader } from '../components/PageHeader'
import { cn } from '../lib/cn'
import { formatBytes, formatCount, formatDuration, formatWhen } from '../lib/format'
import type { BackupHistory, BackupRun, BackupVolume, DatabaseDumps, GitHubMirror } from '../lib/types'
import { useApi } from '../lib/useApi'

const runSeconds = (run: BackupRun) => run.volumes.reduce((sum, v) => sum + v.seconds, 0)

function Outcome({ ok }: { ok: boolean }) {
  return <span className={cn('font-semibold', ok ? 'text-up' : 'text-down')}>{ok ? 'Succeeded' : 'Failed'}</span>
}

function changed(v: BackupVolume): string {
  if (v.bytes == null) return 'no stats'
  const files = v.transfers != null ? ` · ${formatCount(v.transfers)} file${v.transfers === 1 ? '' : 's'}` : ''
  return `${formatBytes(v.bytes)}${files}`
}

export function BackupsPage() {
  const { data, error } = useApi<BackupHistory>('/api/backups', 300_000)
  const { data: mirror } = useApi<GitHubMirror>('/api/github-mirror', 300_000)
  const { data: dumps } = useApi<DatabaseDumps>('/api/database-dumps', 300_000)
  const last = data?.runs[0]
  const recent = data?.runs.slice(0, 30) ?? []
  const succeeded = recent.filter((r) => r.ok).length

  return (
    <>
      <PageHeader title="Backups" subtitle="Nightly rclone runs to the Hetzner storage box, encrypted" />

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
          <dl className="mb-5 grid grid-cols-2 gap-2.5 md:gap-4 xl:grid-cols-4">
            <div className="rounded-[14px] border border-line-soft bg-card px-4 py-3.5">
              <dt className="text-[12.5px] text-muted">Last run</dt>
              <dd className="text-[15px]">
                <Outcome ok={last.ok} /> <span className="text-muted">{formatWhen(last.finished)}</span>
              </dd>
            </div>
            <div className="rounded-[14px] border border-line-soft bg-card px-4 py-3.5">
              <dt className="text-[12.5px] text-muted">Took</dt>
              <dd className="text-[15px] font-semibold">{formatDuration(runSeconds(last))}</dd>
            </div>
            <div className="rounded-[14px] border border-line-soft bg-card px-4 py-3.5">
              <dt className="text-[12.5px] text-muted">Next run due</dt>
              <dd className="text-[15px] font-semibold">{data.next_due ? formatWhen(data.next_due) : 'Unknown'}</dd>
            </div>
            <div className="rounded-[14px] border border-line-soft bg-card px-4 py-3.5">
              <dt className="text-[12.5px] text-muted">Succeeded, last {recent.length} runs</dt>
              <dd className={cn('text-[15px] font-semibold', succeeded < recent.length && 'text-warn')}>
                {succeeded} of {recent.length}
              </dd>
            </div>
          </dl>

          {data.storage_box && <StorageBoxCard box={data.storage_box} />}

          <div className="grid gap-4 md:grid-cols-2">
            {data.volumes.map((summary) => {
              const v = summary.last_run?.volumes.find((x) => x.name === summary.name)
              return (
                <Card key={summary.name} title={summary.name}>
                  {v && (
                    <dl className="grid grid-cols-[auto_minmax(0,1fr)] gap-x-4 gap-y-1.5 text-[13.5px]">
                      <dt className="text-muted">Last run</dt>
                      <dd>
                        <Outcome ok={v.ok} />
                        {!v.ok && <span className="text-muted"> (exit code {v.exit_code})</span>}
                      </dd>
                      <dt className="text-muted">Last success</dt>
                      <dd>{summary.last_success ? formatWhen(summary.last_success) : 'Never recorded'}</dd>
                      <dt className="text-muted">Changed</dt>
                      <dd>{changed(v)}</dd>
                      <dt className="text-muted">Took</dt>
                      <dd>{formatDuration(v.seconds)}</dd>
                      {(v.errors ?? 0) > 0 && (
                        <>
                          <dt className="text-muted">Errors</dt>
                          <dd className="text-down">{v.errors}</dd>
                        </>
                      )}
                    </dl>
                  )}
                  {v?.last_error && (
                    <p className="mt-3 rounded-lg border border-down/40 bg-down/10 px-3 py-2 font-mono text-[12px] break-words text-fg">
                      {v.last_error}
                    </p>
                  )}
                </Card>
              )
            })}
          </div>

          <Card title={`Last ${recent.length} runs`} className="mt-5">
            <RunBars runs={recent} />
            <div className="mt-4 overflow-x-auto">
              <table className="w-full min-w-[34rem] text-[13px]">
                <thead>
                  <tr className="text-left text-[12px] text-faint">
                    <th className="pb-2 font-medium">Finished</th>
                    <th className="pb-2 font-medium">Result</th>
                    <th className="pb-2 text-right font-medium">Took</th>
                    {data.volumes.map((s) => (
                      <th key={s.name} className="pb-2 text-right font-medium">
                        {s.name}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {recent.map((run) => (
                    <tr key={run.started} className="border-t border-line-soft">
                      <td className="py-2">{formatWhen(run.finished)}</td>
                      <td className="py-2">
                        <Outcome ok={run.ok} />
                      </td>
                      <td className="py-2 text-right">{formatDuration(runSeconds(run))}</td>
                      {data.volumes.map((s) => {
                        const v = run.volumes.find((x) => x.name === s.name)
                        return (
                          <td key={s.name} className={cn('py-2 text-right', v && !v.ok && 'text-down')}>
                            {v ? (v.ok ? changed(v) : 'failed') : '–'}
                          </td>
                        )
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
          {data.stale && <StaleNote />}
        </>
      )}

      {dumps && <DumpsCard dumps={dumps} />}
      {dumps && (
        <RestoreCheckCard
          checks={dumps.restore_checks ?? []}
          lastVerified={dumps.last_verified ?? null}
          stale={dumps.stale}
        />
      )}
      {mirror?.enabled && <MirrorCard mirror={mirror} />}
    </>
  )
}
