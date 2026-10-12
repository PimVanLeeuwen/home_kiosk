import { Card, StaleNote } from '../home/Card'
import { cn } from '../../lib/cn'
import { formatWhen } from '../../lib/format'
import type { RestoreCheck } from '../../lib/types'
import { Seal } from '../ui/Seal'

const LABELS: Record<string, string> = {
  'download:databases': 'Download of the dumps',
  'download:hub': 'Download of the hub database',
  ghostfolio: 'Ghostfolio restore',
  hub: 'Hub database opens',
}

type Props = { checks: RestoreCheck[]; lastVerified: string | null; stale: boolean }

/** The monthly proof that the Hetzner copy restores: a seal with the newest check, and its steps as a checklist. */
export function RestoreCheckCard({ checks, lastVerified, stale }: Props) {
  const last = checks[0]

  return (
    <Card
      title="Restore check"
      actions={<span className="text-[11px] font-semibold tracking-[0.08em] text-faint uppercase">Monthly, the 1st</span>}
    >
      {!last ? (
        <p className="text-muted">
          No restore check recorded yet. It runs from root&apos;s crontab on the NAS (see the nas-docker README, Restore
          check).
        </p>
      ) : (
        <>
          <div className="flex items-center gap-3.5">
            <Seal ok={last.ok} label={last.ok ? 'Restore check passed' : 'Restore check failed'} size={64} />
            <dl className="grid grid-cols-[auto_minmax(0,1fr)] gap-x-4 gap-y-1 text-[13.5px]">
              <dt className="text-muted">Last check</dt>
              <dd>
                <span className={cn('font-semibold', last.ok ? 'text-up' : 'text-down')}>{last.ok ? 'Passed' : 'Failed'}</span>{' '}
                <span className="text-muted">{formatWhen(last.finished)}</span>
              </dd>
              <dt className="text-muted">Last verified restore</dt>
              <dd>{lastVerified ? formatWhen(lastVerified) : 'Never'}</dd>
            </dl>
          </div>
          <ol className="mt-4 grid gap-2 border-l border-line pl-4 text-[13px]">
            {last.checks.map((c) => (
              <li key={c.name} className="relative">
                <span
                  aria-hidden="true"
                  className={cn(
                    'absolute top-0.5 -left-[24px] grid size-[15px] place-items-center rounded-full text-[10px] font-bold',
                    c.ok ? 'bg-up/16 text-up' : 'bg-down/18 text-down',
                  )}
                >
                  {c.ok ? '✓' : '×'}
                </span>
                <span className="sr-only">{c.ok ? 'OK' : 'Failed'}</span>
                <span>{LABELS[c.name] ?? c.name}</span>
                <span className={cn('block text-[12px]', c.ok ? 'text-muted' : 'font-mono text-fg')}>{c.detail}</span>
              </li>
            ))}
          </ol>
        </>
      )}
      <p className="mt-3 text-[12px] text-faint">
        The NAS downloads the dumps and the hub database from Hetzner, compares them with the local files and loads them
        into throwaway containers.
      </p>
      {stale && <StaleNote />}
    </Card>
  )
}
