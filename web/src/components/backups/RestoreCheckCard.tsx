import { useEffect, useRef, useState } from 'react'
import { Card } from '../ui/Card'
import { StaleNote } from '../ui/states'
import { ApiError, sendJson } from '../../lib/api'
import { cn } from '../../lib/cn'
import { formatWhen } from '../../lib/format'
import type { RestoreCheck, RestoreRequest } from '../../lib/types'
import { useApi } from '../../lib/useApi'
import { Seal } from '../ui/Seal'

const LABELS: Record<string, string> = {
  'download:databases': 'Download of the dumps',
  'download:hub': 'Download of the hub database',
  ghostfolio: 'Ghostfolio restore',
  hub: 'Hub database opens',
}

type Props = { checks: RestoreCheck[]; lastVerified: string | null; stale: boolean; onFinished?: () => void }

/** The monthly proof that the Hetzner copy restores: a seal with the newest check, and its steps as a checklist. */
export function RestoreCheckCard({ checks, lastVerified, stale, onFinished }: Props) {
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
      <RunNow onFinished={onFinished} />
      <p className="mt-3 text-[12px] text-faint">
        The NAS downloads the dumps and the hub database from Hetzner, compares them with the local files and loads them
        into throwaway containers.
      </p>
      {stale && <StaleNote />}
    </Card>
  )
}

/**
 * Asks the NAS for a check now (the hub cannot run it: it leaves a request that a cron
 * line on the NAS picks up within 5 minutes; at most one check an hour).
 */
function RunNow({ onFinished }: { onFinished?: () => void }) {
  const request = useApi<RestoreRequest>('/api/backups/restore-check', 30_000)
  const [refused, setRefused] = useState<string>()
  const state = request.data?.state ?? 'idle'
  const was = useRef(state)

  useEffect(() => {
    if (was.current !== 'idle' && state === 'idle') onFinished?.() // the new record is in
    was.current = state
  }, [state, onFinished])

  async function ask() {
    setRefused(undefined)
    try {
      await sendJson('POST', '/api/backups/restore-check', {})
    } catch (err) {
      setRefused(err instanceof ApiError ? err.message : 'Asking the NAS failed')
    }
    request.reload()
  }

  return (
    <div className="mt-4 flex flex-wrap items-center gap-3">
      <button
        type="button"
        disabled={state !== 'idle'}
        onClick={ask}
        className="rounded-[10px] bg-accent px-3.5 py-2 text-[13px] font-medium text-white disabled:opacity-40"
      >
        Run a check now
      </button>
      {state === 'requested' && (
        <span role="status" className="text-[12.5px] text-muted">
          Asked{request.data?.since ? ` ${formatWhen(request.data.since)}` : ''}; the NAS starts it within 5 minutes
        </span>
      )}
      {state === 'running' && (
        <span role="status" className="text-[12.5px] text-muted">
          Running on the NAS…
        </span>
      )}
      {refused && (
        <span role="alert" className="text-[12.5px] text-down">
          {refused}
        </span>
      )}
    </div>
  )
}
