import { Card, StaleNote } from '../home/Card'
import { cn } from '../../lib/cn'
import { formatBytes, formatCount, formatWhen } from '../../lib/format'
import type { GitHubMirror } from '../../lib/types'

/** The nightly GitHub mirror on the Backups page: last run, size and what failed. */
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
      <p className="mb-3 text-[13px] text-muted">
        A bare git copy of every repo of {mirror.owners.map((o) => o.login).join(' and ') || 'the mirrored owners'}{' '}
        (no forks), kept in <span className="font-mono text-[12px]">/volume3/backups/github</span> and taken to Hetzner by
        the nightly backup. Repos deleted on GitHub are deleted here too.
      </p>
      {!last ? (
        <p className="text-muted">
          No run yet.{mirror.next_due ? ` The first one is due ${formatWhen(mirror.next_due)}.` : ''}
        </p>
      ) : (
        <dl className="grid grid-cols-[auto_minmax(0,1fr)] gap-x-4 gap-y-1.5 text-[13.5px]">
          <dt className="text-muted">Last run</dt>
          <dd>
            <span className={cn('font-semibold', last.ok ? 'text-up' : 'text-down')}>
              {last.ok ? 'Succeeded' : 'Failed'}
            </span>{' '}
            <span className="text-muted">{formatWhen(last.finished)}</span>
          </dd>
          <dt className="text-muted">Last complete</dt>
          <dd>{mirror.last_success ? formatWhen(mirror.last_success) : 'Never'}</dd>
          <dt className="text-muted">Repos</dt>
          <dd>
            {mirror.owners.map((o) => `${o.label} ${formatCount(o.repos.length)}`).join(' · ')}
            {last.failed > 0 && <span className="text-down"> · {last.failed} failed</span>}
          </dd>
          <dt className="text-muted">Size</dt>
          <dd>{formatBytes(last.bytes)}</dd>
          {removed.length > 0 && (
            <>
              <dt className="text-muted">Removed</dt>
              <dd>{removed.join(', ')}</dd>
            </>
          )}
          <dt className="text-muted">Succeeded, last {recent.length}</dt>
          <dd className={cn(succeeded < recent.length && 'text-warn')}>
            {succeeded} of {recent.length}
          </dd>
          <dt className="text-muted">Next run due</dt>
          <dd>{mirror.next_due ? formatWhen(mirror.next_due) : 'Unknown'}</dd>
        </dl>
      )}
      {problems.length > 0 && (
        <ul className="mt-3 space-y-1 rounded-lg border border-down/40 bg-down/10 px-3 py-2 font-mono text-[12px] break-words text-fg">
          {problems.map((p) => (
            <li key={p}>{p}</li>
          ))}
        </ul>
      )}
      {mirror.stale && <StaleNote />}
    </Card>
  )
}
