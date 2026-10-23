import { POOL_FULL_PCT, type Attention } from './attention'
import { formatWhen } from './format'
import type { CardState, FoldedCardId } from './homeOrder'
import { backupsState, nasState, outsideState, servicesState } from './homeStates'
import { troubled } from './outside'
import type { BackupHistory, Nas, OutsideServices, OutsideState, Service, ServiceStatus } from './types'

export type ChipTone = 'ok' | 'warn' | 'down' | 'unknown'
/** One segment of a chip's small meter. */
export type Segment = 'up' | 'accent' | 'warn' | 'down' | 'off'

export interface Chip {
  id: FoldedCardId | 'alerts'
  label: string
  value: string
  tone: ChipTone
  meter: Segment[]
}

/** Nights in the backup chip's meter. */
export const NIGHTS = 14
/** More services than this share segments, so the meter stays readable. */
const MAX_SEGMENTS = 24

const toneOf = (state: CardState, known: boolean): ChipTone =>
  !known ? 'unknown' : state === 'down' ? 'down' : state === 'warn' ? 'warn' : 'ok'

const SERVICE_SEGMENT: Record<ServiceStatus, Segment> = {
  up: 'up',
  starting: 'accent',
  unhealthy: 'warn',
  down: 'down',
  missing: 'down',
  unknown: 'off',
}
const OUTSIDE_SEGMENT: Record<OutsideState, Segment> = {
  ok: 'up',
  maintenance: 'accent',
  degraded: 'warn',
  outage: 'down',
  unknown: 'off',
}
const SEGMENT_RANK: Record<Segment, number> = { up: 0, accent: 1, off: 2, warn: 3, down: 4 }

/** Segments best first, so trouble sits at the end of the meter; squeezed when there are many. */
function squeeze(segments: Segment[]): Segment[] {
  const sorted = [...segments].sort((a, b) => SEGMENT_RANK[a] - SEGMENT_RANK[b])
  if (sorted.length <= MAX_SEGMENTS) return sorted
  return Array.from({ length: MAX_SEGMENTS }, (_, i) => sorted[Math.floor(((i + 1) * sorted.length) / MAX_SEGMENTS) - 1])
}

interface Sources {
  nas: Nas | undefined
  services: Service[] | undefined
  backups: BackupHistory | undefined
  outside: OutsideServices | undefined
  attention: Attention[]
  now: Date
}

/** The status strip's chips: NAS, Services, Backups and Outside services hold their folded card; Alerts only reports. */
export function homeChips({ nas, services, backups, outside, attention, now }: Sources): Chip[] {
  const nasTone = toneOf(nasState(nas), !!nas)
  const used = nas?.storage.used_pct ?? 0
  const storageFull = !!nas?.storage.pools.some((p) => p.used_pct >= POOL_FULL_PCT)

  const servicesTone = toneOf(servicesState(services), !!services)
  // External links have no container, so no state to count.
  const watched = services?.filter((s) => s.status !== 'unknown')
  const up = watched?.filter((s) => s.status === 'up').length ?? 0

  const backupTone = toneOf(backupsState(nas, now), !!nas && nas.backup.status !== 'unknown')
  const nights = (backups?.runs ?? []).slice(0, NIGHTS).reverse().map((r): Segment => (r.ok ? 'up' : 'down'))
  const backupAt = nas?.backup.at ? formatWhen(nas.backup.at) : null

  const outsideProblems = outside ? troubled(outside.services).length : 0
  const worst = attention[0]

  return [
    {
      id: 'nas',
      label: 'NAS',
      value: !nas ? 'Unknown' : nasTone === 'down' ? 'Disk failing' : nasTone === 'warn' ? 'Needs a look' : 'Healthy',
      tone: nasTone,
      meter: nas ? Array.from({ length: 10 }, (_, i) => (i < Math.round(used / 10) ? (storageFull ? 'warn' : 'accent') : 'off')) : [],
    },
    {
      id: 'services',
      label: 'Services',
      value: watched ? `${up} / ${watched.length} up` : 'Unknown',
      tone: servicesTone,
      meter: squeeze((watched ?? []).map((s) => SERVICE_SEGMENT[s.status])),
    },
    {
      id: 'backups',
      label: 'Last backup',
      value: !backupAt ? 'Unknown' : nas?.backup.status === 'fail' ? `Failed ${backupAt}` : backupAt,
      tone: backupTone,
      meter: backups ? [...Array<Segment>(Math.max(0, NIGHTS - nights.length)).fill('off'), ...nights] : [],
    },
    {
      id: 'outside',
      label: 'Outside services',
      value: !outside ? 'Unknown' : outsideProblems === 0 ? 'All clear' : `${outsideProblems} ${outsideProblems === 1 ? 'problem' : 'problems'}`,
      tone: toneOf(outsideState(outside), !!outside),
      meter: squeeze((outside?.services ?? []).map((s) => OUTSIDE_SEGMENT[s.state])),
    },
    {
      id: 'alerts',
      label: 'Alerts',
      value: !worst ? 'None' : attention.length === 1 ? worst.text : `${worst.text} +${attention.length - 1}`,
      tone: worst?.level ?? 'ok',
      meter: [],
    },
  ]
}
