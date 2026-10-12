import type { Tone } from '../components/ui/tones'
import { BACKUP_MAX_AGE_HOURS } from './attention'
import type { BackupRun } from './types'

/** How many nights the strip on Home and the Backups page shows. */
export const NIGHTS = 30
/** A night this much slower than usual stands out in amber. */
export const SLOW_FACTOR = 1.3
/** The backup_missing rule's default: a restore check older than this needs a new one. */
export const RESTORE_MAX_DAYS = 45

/** A run's wall-clock duration in seconds. */
export const runSeconds = (run: BackupRun) => (new Date(run.finished).getTime() - new Date(run.started).getTime()) / 1000

function median(values: number[]): number {
  const sorted = [...values].sort((a, b) => a - b)
  return sorted[Math.floor(sorted.length / 2)] ?? 0
}

/**
 * The last nights oldest first as minutes, failed ones red and slow ones amber,
 * and which one to name under the strip: the newest failure, else the first slow night.
 */
export function nightStrip(runs: BackupRun[]) {
  const shown = runs.slice(0, NIGHTS).reverse()
  const minutes = shown.map((r) => runSeconds(r) / 60)
  const usual = median(minutes)
  const marks: Record<number, Tone> = {}
  shown.forEach((r, i) => {
    if (!r.ok) marks[i] = 'down'
    else if (usual > 0 && minutes[i] > usual * SLOW_FACTOR) marks[i] = 'warn'
  })
  const failedAt = Object.keys(marks).map(Number).filter((i) => marks[i] === 'down').pop()
  const slowAt = Object.keys(marks).map(Number).find((i) => marks[i] === 'warn')
  return {
    minutes,
    marks,
    markAt: failedAt ?? slowAt,
    markLabel: failedAt != null ? 'failed' : slowAt != null ? 'slow' : undefined,
  }
}

export type BackupVerdict = 'safe' | 'failed' | 'overdue'

/** All safe, failed, or overdue (no run in BACKUP_MAX_AGE_HOURS), from the newest run. */
export function backupVerdict(last: BackupRun, now: Date): BackupVerdict {
  if (!last.ok) return 'failed'
  return now.getTime() - new Date(last.finished).getTime() > BACKUP_MAX_AGE_HOURS * 3_600_000 ? 'overdue' : 'safe'
}

export const VERDICT_PILL: Record<BackupVerdict, { tone: Tone; label: string }> = {
  safe: { tone: 'up', label: 'All safe' },
  failed: { tone: 'down', label: 'Failed' },
  overdue: { tone: 'warn', label: 'Overdue' },
}
