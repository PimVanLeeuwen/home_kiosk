import { Card } from '../ui/Card'
import { StaleNote } from '../ui/states'
import { cn } from '../../lib/cn'
import { formatBytes, formatCount, formatWhen } from '../../lib/format'
import type { GitHubMirror } from '../../lib/types'
import { RunDots } from '../ui/RunDots'

function Tile({ value, label, bad }: { value: string; label: string; bad?: boolean }) {
  return (
    <div
      className={cn(
        'min-w-0 rounded-[10px] border px-3 py-2',
        bad ? 'border-down/40 bg-linear-to-br from-down/12 to-down/[0.03]' : 'border-glass-line bg-glass',
      )}
    >
      <p className={cn('text-[18px] leading-tight font-semibold', bad && 'text-down')}>{value}</p>
      <p className="truncate text-[12px] text-muted">{label}</p>
    </div>
  )
}

/** The nightly GitHub mirror on the Backups page: the owners and their repos, the recent runs and what failed. */
export function MirrorCard({ mirror }: { mirror: GitHubMirror }) {
  const last = mirror.runs[0]
  const recent = mirror.runs.slice(0, 30)
  const succeeded = recent.filter((r) => r.ok).length
  const failed = mirror.owners.flatMap((o) => o.repos.filter((r) => !r.ok && r.error))
  const problems = [
    ...(mirror.error ? [mirror.error] : []),
    ...mirror.owners.filter((o) => o.error).map((o) => `${o.label}: ${o.error}`),
    ...failed.map((r) => `${r.full_name}: ${r.error}`),
  ]
  const removed = mirror.owners.flatMap((o) => o.removed)

  return (
    <Card title="GitHub mirror" link={{ to: '/repos', label: 'Repos' }} className="mt-5">
      <div className="grid items-start gap-4 lg:grid-cols-[minmax(0,1.2fr)_minmax(0,1fr)] lg:gap-6">
        <div className="min-w-0">
          {last && (
            <div className="flex flex-wrap gap-2">
              {mirror.owners.map((o) => (
                <Tile key={o.login} value={formatCount(o.repos.length)} label={`${o.label} repos`} />
              ))}
              {last.failed > 0 && <Tile value={formatCount(last.failed)} label="failed" bad />}
              <Tile value={formatBytes(last.bytes)} label="on the NAS" />
            </div>
          )}
          <p className="mt-3 text-[12.5px] text-muted">
            A bare git copy of every repo of {mirror.owners.map((o) => o.login).join(' and ') || 'the mirrored owners'}{' '}
            (no forks), kept in <span className="font-mono text-[12px]">/volume3/backups/github</span> and taken to Hetzner
            by the nightly backup. Repos deleted on GitHub are deleted here too.
          </p>
        </div>
        <div className="min-w-0">
          {!last ? (
            <p className="text-muted">
              No run yet.{mirror.next_due ? ` The first one is due ${formatWhen(mirror.next_due)}.` : ''}
            </p>
          ) : (
            <dl className="grid grid-cols-[auto_minmax(0,1fr)] gap-x-4 gap-y-1.5 text-[13.5px]">
              <dt className="text-muted">Last run</dt>
              <dd>
                <span className={cn('font-semibold', last.ok ? 'text-up' : 'text-down')}>{last.ok ? 'Succeeded' : 'Failed'}</span>{' '}
                <span className="text-muted">{formatWhen(last.finished)}</span>
              </dd>
              <dt className="text-muted">Last complete</dt>
              <dd>{mirror.last_success ? formatWhen(mirror.last_success) : 'Never'}</dd>
              <dt className="text-muted">Next run due</dt>
              <dd>{mirror.next_due ? formatWhen(mirror.next_due) : 'Unknown'}</dd>
              <dt className="text-muted">Succeeded, last {recent.length}</dt>
              <dd className="flex flex-wrap items-center gap-x-2.5 gap-y-1">
                <span className={cn(succeeded < recent.length && 'text-warn')}>
                  {succeeded} of {recent.length}
                </span>
                <RunDots runs={recent} label={`The last ${recent.length} mirror runs, oldest first`} />
              </dd>
              {removed.length > 0 && (
                <>
                  <dt className="text-muted">Removed</dt>
                  <dd className="break-words">{removed.join(', ')}</dd>
                </>
              )}
            </dl>
          )}
          {problems.length > 0 && (
            <ul className="mt-3 space-y-1 rounded-lg border border-down/40 bg-down/10 px-3 py-2 font-mono text-[12px] break-words text-fg">
              {problems.map((p) => (
                <li key={p}>{p}</li>
              ))}
            </ul>
          )}
        </div>
      </div>
      {mirror.stale && <StaleNote />}
    </Card>
  )
}
