import { cn } from '../../lib/cn'
import { formatDuration, formatWhen } from '../../lib/format'
import type { BackupHistory, BackupRun } from '../../lib/types'
import { changed, volumeColour } from '../../lib/volumes'
import { Card } from '../ui/Card'
import { GlowDot } from '../ui/GlowDot'

/** The time the volumes took together, as the run's "Took". */
const volumeSeconds = (run: BackupRun) => run.volumes.reduce((sum, v) => sum + v.seconds, 0)

interface Props {
  runs: BackupRun[]
  volumes: BackupHistory['volumes']
}

/** The recent runs as a table with an LED and a bar per run: a segment per volume, so a slow volume shows. */
export function RunHistoryCard({ runs, volumes }: Props) {
  const longest = Math.max(1, ...runs.map(volumeSeconds))
  const index = new Map(volumes.map((s, i) => [s.name, i]))
  return (
    <Card
      title={`Last ${runs.length} runs`}
      className="mt-5"
      actions={<span className="text-label font-semibold tracking-[0.08em] text-faint uppercase">How long each volume took</span>}
    >
      <p className="mb-2.5 flex flex-wrap gap-x-3.5 gap-y-1 text-label text-muted" aria-hidden="true">
        {volumes.map((s, i) => (
          <span key={s.name} className="flex items-center gap-1.5">
            <i className="inline-block size-[9px] rounded-[3px]" style={{ backgroundColor: volumeColour(i) }} />
            {s.name}
          </span>
        ))}
      </p>
      <div className="overflow-x-auto">
        <table className="w-full text-small">
          <caption className="sr-only">Each run with its result, how long each volume took and what it changed</caption>
          <thead>
            <tr className="text-left text-label text-faint">
              <th className="w-5 pb-2 font-medium">
                <span className="sr-only">Result</span>
              </th>
              <th className="pr-3 pb-2 font-medium">Finished</th>
              <th className="w-[30%] pr-3 pb-2 font-medium">Volumes</th>
              <th className="pr-3 pb-2 font-medium whitespace-nowrap">Took</th>
              {volumes.map((s) => (
                <th key={s.name} className="hidden pb-2 pl-3 text-right font-medium sm:table-cell">
                  {s.name}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {runs.map((run) => (
              <tr key={run.started} className={cn('border-t border-line-soft', !run.ok && 'bg-down/6')}>
                <td className="py-2">
                  <GlowDot tone={run.ok ? 'up' : 'down'} className="size-[7px]" />
                  <span className="sr-only">{run.ok ? 'Succeeded' : 'Failed'}</span>
                </td>
                <td className="py-2 pr-3 whitespace-nowrap">{formatWhen(run.finished)}</td>
                <td className="py-2 pr-3">
                  <span
                    className="flex h-[7px] gap-0.5 overflow-hidden rounded-full"
                    style={{ width: `${Math.max(4, (volumeSeconds(run) / longest) * 100)}%` }}
                    aria-hidden="true"
                  >
                    {run.volumes.map((v) => (
                      <i
                        key={v.name}
                        className="block h-full"
                        style={{
                          flexGrow: Math.max(v.seconds, 1),
                          backgroundColor: v.ok ? volumeColour(index.get(v.name) ?? 0) : 'var(--color-down)',
                        }}
                      />
                    ))}
                  </span>
                </td>
                <td className="py-2 pr-3 whitespace-nowrap text-muted">{formatDuration(volumeSeconds(run))}</td>
                {volumes.map((s) => {
                  const v = run.volumes.find((x) => x.name === s.name)
                  return (
                    <td
                      key={s.name}
                      className={cn('hidden py-2 pl-3 text-right whitespace-nowrap sm:table-cell', v && !v.ok ? 'text-down' : 'text-muted')}
                    >
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
  )
}
