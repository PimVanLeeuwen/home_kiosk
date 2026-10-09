import { Card, StaleNote } from '../home/Card'
import { cn } from '../../lib/cn'
import { formatWhen } from '../../lib/format'
import type { RestoreCheck } from '../../lib/types'

const LABELS: Record<string, string> = {
  'download:databases': 'Download of the dumps',
  'download:hub': 'Download of the hub database',
  ghostfolio: 'Ghostfolio restore',
  hub: 'Hub database opens',
}

type Props = { checks: RestoreCheck[]; lastVerified: string | null; stale: boolean }

/** The monthly proof that the Hetzner copy restores: the newest check, step by step. */
export function RestoreCheckCard({ checks, lastVerified, stale }: Props) {
  const last = checks[0]

  return (
    <Card title="Restore check" className="mt-5">
      <p className="mb-3 text-[13px] text-muted">
        Once a month the NAS downloads the dumps and the hub database from Hetzner, compares them with the local files,
        and loads them into throwaway containers.
      </p>
      {!last ? (
        <p className="text-muted">
          No restore check recorded yet. It runs from root&apos;s crontab on the NAS (see the nas-docker README, Restore
          check).
        </p>
      ) : (
        <>
          <dl className="grid grid-cols-[auto_minmax(0,1fr)] gap-x-4 gap-y-1.5 text-[13.5px]">
            <dt className="text-muted">Last check</dt>
            <dd>
              <span className={cn('font-semibold', last.ok ? 'text-up' : 'text-down')}>
                {last.ok ? 'Passed' : 'Failed'}
              </span>{' '}
              <span className="text-muted">{formatWhen(last.finished)}</span>
            </dd>
            <dt className="text-muted">Last verified restore</dt>
            <dd>{lastVerified ? formatWhen(lastVerified) : 'Never'}</dd>
          </dl>
          <ul className="mt-3 space-y-1.5 text-[13px]">
            {last.checks.map((c) => (
              <li key={c.name} className="flex flex-wrap gap-x-2">
                <span className={cn('w-12 shrink-0 font-semibold', c.ok ? 'text-up' : 'text-down')}>
                  {c.ok ? 'OK' : 'Failed'}
                </span>
                <span>{LABELS[c.name] ?? c.name}</span>
                <span className={cn('basis-full pl-14 text-[12.5px]', c.ok ? 'text-muted' : 'font-mono text-fg')}>
                  {c.detail}
                </span>
              </li>
            ))}
          </ul>
        </>
      )}
      {stale && <StaleNote />}
    </Card>
  )
}
