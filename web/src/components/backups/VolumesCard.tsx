import { useId } from 'react'
import { cn } from '../../lib/cn'
import { formatDuration, formatWhen } from '../../lib/format'
import type { BackupHistory } from '../../lib/types'
import { changed, volumeColour } from '../../lib/volumes'
import { Card } from '../ui/Card'
import { GlowDot } from '../ui/GlowDot'

type Summary = BackupHistory['volumes'][number]

function VolumeTile({ summary, index }: { summary: Summary; index: number }) {
  const id = useId()
  const v = summary.last_run?.volumes.find((x) => x.name === summary.name)
  const bad = !!v && !v.ok
  return (
    <section
      aria-labelledby={id}
      className={cn(
        'grid content-start gap-1.5 rounded-[12px] border p-3 text-caption',
        bad ? 'border-down/40 bg-linear-to-br from-down/12 to-down/[0.03]' : 'border-glass-line bg-glass',
      )}
    >
      <div className="flex items-center gap-2">
        <GlowDot tone={!v ? 'muted' : v.ok ? 'up' : 'down'} halo={bad} className="size-[7px]" />
        <h3 id={id} className="font-mono text-small font-semibold">
          {summary.name}
        </h3>
        <span aria-hidden="true" className="ml-auto size-[9px] rounded-[3px]" style={{ backgroundColor: volumeColour(index) }} />
      </div>
      {v && (
        <dl className="grid grid-cols-[auto_minmax(0,1fr)] gap-x-3 gap-y-0.5 [&_dd]:text-right [&_dt]:text-muted">
          <dt>Last run</dt>
          <dd>
            <span className={cn('font-semibold', v.ok ? 'text-up' : 'text-down')}>{v.ok ? 'Succeeded' : 'Failed'}</span>
            {!v.ok && <span className="text-muted"> (exit code {v.exit_code})</span>}
          </dd>
          <dt>Last success</dt>
          <dd>{summary.last_success ? formatWhen(summary.last_success) : 'Never recorded'}</dd>
          <dt>Changed</dt>
          <dd>{changed(v)}</dd>
          <dt>Took</dt>
          <dd>{formatDuration(v.seconds)}</dd>
          {(v.errors ?? 0) > 0 && (
            <>
              <dt>Errors</dt>
              <dd className="text-down">{v.errors}</dd>
            </>
          )}
        </dl>
      )}
      {v?.last_error && (
        <p className="rounded-lg border border-down/40 bg-down/10 px-2.5 py-1.5 font-mono text-label break-words text-fg">
          {v.last_error}
        </p>
      )}
    </section>
  )
}

/** Each volume's last run as a glass tile: an LED, its colour in the run history, and what it did. */
export function VolumesCard({ volumes }: { volumes: Summary[] }) {
  return (
    <Card title="Volumes" actions={<span className="text-label font-semibold tracking-[0.08em] text-faint uppercase">Last run</span>}>
      <div className="grid gap-2.5 sm:grid-cols-2 xl:grid-cols-3">
        {volumes.map((summary, i) => (
          <VolumeTile key={summary.name} summary={summary} index={i} />
        ))}
      </div>
    </Card>
  )
}
