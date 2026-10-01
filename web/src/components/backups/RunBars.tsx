import type { BackupRun } from '../../lib/types'
import { formatDuration, formatWhen } from '../../lib/format'

const runSeconds = (run: BackupRun) => run.volumes.reduce((sum, v) => sum + v.seconds, 0)

/** Duration per run as bars, oldest left; failed runs in red. */
export function RunBars({ runs }: { runs: BackupRun[] }) {
  const shown = [...runs].reverse()
  const longest = Math.max(...shown.map(runSeconds), 1)
  const failed = shown.filter((r) => !r.ok).length
  const label = `Duration of the last ${shown.length} runs; ${failed ? `${failed} failed` : 'all succeeded'}.`

  return (
    <div role="img" aria-label={label} className="flex h-24 items-end gap-[3px]">
      {shown.map((run) => (
        <span
          key={run.started}
          title={`${formatWhen(run.started)}: ${run.ok ? 'succeeded' : 'failed'}, ${formatDuration(runSeconds(run))}`}
          className={run.ok ? 'min-w-[4px] flex-1 rounded-t-[2px] bg-up/80' : 'min-w-[4px] flex-1 rounded-t-[2px] bg-down'}
          style={{ height: `${Math.max(6, (runSeconds(run) / longest) * 100)}%` }}
        />
      ))}
    </div>
  )
}
