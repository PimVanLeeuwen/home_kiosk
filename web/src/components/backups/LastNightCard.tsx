import type { ReactNode } from 'react'
import { nightStrip, runSeconds } from '../../lib/backups'
import { formatBytes, formatDuration, formatWhen } from '../../lib/format'
import type { BackupHistory, BackupRun, DatabaseDumps } from '../../lib/types'
import { Card } from '../ui/Card'
import { BarStrip } from '../ui/BarStrip'
import { FlowLine } from '../ui/FlowLine'
import { Seal } from '../ui/Seal'
import { RestoreLine } from './RestoreLine'

function Fact({ label, children }: { label: string; children: ReactNode }) {
  return (
    // One line on a phone (label left, value right), a small tile from sm up.
    <div className="flex min-w-0 items-baseline justify-between gap-3 rounded-[10px] border border-glass-line bg-glass px-2.5 py-2 sm:block">
      <dt className="shrink-0 text-micro font-semibold tracking-[0.08em] text-faint uppercase">{label}</dt>
      <dd className="mt-px truncate text-body font-semibold">{children}</dd>
    </div>
  )
}

interface Props {
  last: BackupRun
  history: BackupHistory
  dumps: DatabaseDumps | undefined
  now: Date
}

/** Last night at the top of the Backups page: a seal, the route to Hetzner, three facts and the nights before. */
export function LastNightCard({ last, history, dumps, now }: Props) {
  const bytes = last.volumes.reduce((sum, v) => sum + (v.ok && v.bytes != null ? v.bytes : 0), 0)
  const failed = last.volumes.filter((v) => !v.ok)
  const recent = history.runs.slice(0, 30)
  const succeeded = recent.filter((r) => r.ok).length
  const strip = nightStrip(history.runs)
  const n = strip.minutes.length

  return (
    <Card
      title="Last night"
      actions={<span className="text-label font-semibold tracking-[0.08em] text-faint uppercase">Hetzner · encrypted</span>}
    >
      <div className="grid items-center gap-5 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.15fr)] lg:gap-7">
        <div className="min-w-0">
          <div className="flex items-center gap-4">
            <Seal ok={last.ok} label={last.ok ? 'Backup succeeded' : 'Backup failed'} size={80} />
            <div className="min-w-0">
              <p className="text-stat leading-tight font-semibold">
                <span className={last.ok ? 'text-up' : 'text-down'}>{last.ok ? 'Succeeded' : 'Failed'}</span>{' '}
                <span className="text-body font-normal text-muted">{formatWhen(last.finished)}</span>
              </p>
              <p className="text-small text-muted">
                {last.volumes.length} {last.volumes.length === 1 ? 'volume' : 'volumes'} · took {formatDuration(runSeconds(last))}
                {bytes > 0 && ` · ${formatBytes(bytes)} changed`}
              </p>
              {failed.length > 0 && (
                <p className="text-small text-down">
                  {failed.map((v) => `${v.name}${v.last_error ? `: ${v.last_error}` : ' failed'}`).join(' · ')}
                </p>
              )}
            </div>
          </div>
          <div className="my-4">
            <FlowLine from="NAS" to="Hetzner · encrypted" ok={last.ok} />
          </div>
          <dl className="grid gap-2 sm:grid-cols-3">
            <Fact label="Next run">{history.next_due ? formatWhen(history.next_due) : 'Unknown'}</Fact>
            <Fact label={`Last ${recent.length}`}>
              <span className={succeeded < recent.length ? 'text-warn' : undefined}>
                {succeeded} of {recent.length} ok
              </span>
            </Fact>
            <Fact label="Restore">
              {dumps?.last_verified || dumps?.restore_checks?.length ? <RestoreLine dumps={dumps} now={now} short /> : 'Not checked yet'}
            </Fact>
          </dl>
        </div>
        <BarStrip
          values={strip.minutes}
          label={`Backup durations, last ${n} ${n === 1 ? 'night' : 'nights'}`}
          marks={strip.marks}
          markLabel={strip.markLabel === 'slow' ? 'a slow night' : strip.markLabel}
          markAt={strip.markAt}
          start={`${n} ${n === 1 ? 'night' : 'nights'}`}
          end="last night"
          height={110}
        />
      </div>
    </Card>
  )
}
