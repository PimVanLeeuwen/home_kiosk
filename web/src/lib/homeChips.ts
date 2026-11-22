import { POOL_FULL_PCT, type Attention } from './attention'
import { formatPercent, formatWhen } from './format'
import type { CardState, FoldedCardId } from './homeOrder'
import { backupsState, dnsState, nasState, outsideState, servicesState } from './homeStates'
import { troubled } from './outside'
import type { Tone } from '../components/ui/tones'
import type { BackupHistory, DnsStats, Nas, OutsideServices, OutsideState, Service, ServiceStatus } from './types'

/** A chip's state in the hub's tones: up while all is well, muted while unknown. */
export type ChipTone = Extract<Tone, 'up' | 'warn' | 'down' | 'muted'>
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
  !known ? 'muted' : state === 'down' ? 'down' : state === 'warn' ? 'warn' : 'up'

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
  dns: DnsStats | undefined
  attention: Attention[]
  now: Date
}

/** The status strip's chips: NAS, Services, Backups, Outside services and DNS hold their folded card; Alerts only reports. */
export function homeChips({ nas, services, backups, outside, dns, attention, now }: Sources): Chip[] {
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
      value: !backupAt ? 'Unknown' : nas?.backup.status === 'fail' ? 'Failed' : backupAt,
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
      id: 'dns',
      label: 'Ads blocked',
      value: dnsValue(dns),
      tone: toneOf(dnsState(dns), !!dns),
      // An hour without a single query is a gap: AdGuard was not answering.
      meter: (dns?.hours ?? []).map((h): Segment => (h.queries > 0 ? 'accent' : 'off')),
    },
    {
      id: 'alerts',
      label: 'Alerts',
      value: !worst ? 'None' : attention.length === 1 ? worst.text : `${worst.text} +${attention.length - 1}`,
      tone: worst?.level ?? 'up',
      meter: [],
    },
  ]
}

function dnsValue(dns: DnsStats | undefined): string {
  if (!dns) return 'Unknown'
  if (!dns.answering) return 'Down'
  if (!dns.protection) return 'Paused'
  return dns.share == null ? 'None yet' : formatPercent(dns.share)
}

/**
 * Today's healthy line: the folded cards that have nothing to report, in one sentence
 * ("The NAS is healthy, 19 of 19 services up, last backup today 03:03, ..."); null when none is.
 */
export function healthySummary(chips: Chip[], folded: FoldedCardId[]): string | null {
  const phrase = (chip: Chip): string | null => {
    if (chip.tone !== 'up' || !(folded as string[]).includes(chip.id)) return null
    switch (chip.id) {
      case 'nas':
        return 'the NAS is healthy'
      case 'services':
        return `${chip.value.replace(' / ', ' of ').replace(/ up$/, '')} services up`
      case 'backups':
        return `last backup ${chip.value}`
      case 'outside':
        return 'outside services all clear'
      case 'dns':
        return chip.value.endsWith('%') ? `${chip.value} of lookups blocked` : 'ad blocking on'
      default:
        return null
    }
  }
  const phrases = chips.map(phrase).filter((p): p is string => p !== null)
  if (!phrases.length) return null
  const line = `${phrases.join(', ')}.`
  return line[0].toUpperCase() + line.slice(1)
}
