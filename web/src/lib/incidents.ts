import { sendJson } from './api'
import { PATHS } from './paths'
import type { Tone } from '../components/ui/tones'
import type { FoldedCardId } from './homeOrder'
import type { Incident } from './types'

const DAY = 86_400_000
const weekday = new Intl.DateTimeFormat('en-GB', { weekday: 'narrow' })

/** "3 h", "2 days": how long something has lasted. */
export function lasted(ms: number): string {
  const hours = Math.floor(ms / 3_600_000)
  if (hours < 1) return `${Math.max(1, Math.round(ms / 60_000))} min`
  if (hours < 48) return `${hours} h`
  return `${Math.floor(hours / 24)} days`
}

/** The open alerts' colour: red only while one is an error, amber for warnings, violet for the rest. */
export function openTone(open: Incident[]): Tone {
  if (open.some((i) => i.severity === 'error')) return 'down'
  return open.some((i) => i.severity === 'warning') ? 'warn' : 'accent'
}

/** The last seven days, today last, each with the worst alert that was open on it. */
export function weekOf(incidents: Incident[], now: Date) {
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime()
  return Array.from({ length: 7 }, (_, i) => {
    const start = today - (6 - i) * DAY
    const end = start + DAY
    const that = incidents.filter(
      (x) => new Date(x.opened_at).getTime() < end && (x.resolved_at ? new Date(x.resolved_at).getTime() : now.getTime()) >= start,
    )
    const worst = that.some((x) => x.severity === 'error') ? 'error' : that.some((x) => x.severity === 'warning') ? 'warning' : null
    return { label: weekday.format(new Date(start)), worst, today: i === 6 }
  })
}

/**
 * The page each alert rule is about (collector/app/alerts/rules.py), where its attention row
 * leads and where the space and tab get their dot. A rule left out leads to Alerts.
 */
const RULE_PATH: Record<string, string> = {
  disk_space: PATHS.nas,
  smart: PATHS.nas,
  exposure: PATHS.nas,
  port_scan: PATHS.nas,
  container_health: PATHS.docker,
  outside_services: PATHS.services,
  adguard: PATHS.services,
  backup_missing: PATHS.backups,
  storage_box: PATHS.backups,
  token_expiry: PATHS.repos,
  train: PATHS.today,
  apple_offline: PATHS.today,
  desk_panels: `${PATHS.settings}/desk-panels`,
  portfolio_move: PATHS.portfolio,
}

/** The page an incident is about. */
export const incidentPath = (incident: Pick<Incident, 'rule'>): string => RULE_PATH[incident.rule] ?? PATHS.alerts

/** What needs a look: open warnings and errors nobody dismissed, errors first, then the longest open. */
export function needsLook(incidents: Incident[] | undefined): Incident[] {
  if (!Array.isArray(incidents)) return []
  return incidents
    .filter((i) => !i.resolved_at && !i.dismissed_at && (i.severity === 'error' || i.severity === 'warning'))
    .sort((a, b) => (a.severity === b.severity ? a.opened_at.localeCompare(b.opened_at) : a.severity === 'error' ? -1 : 1))
}

/** Whether a page (and everything under it) has something that needs a look, and how bad: for the dots. */
export function lookAt(open: Incident[], path: string): 'down' | 'warn' | null {
  const here = open.filter((i) => {
    const to = incidentPath(i)
    return path === '/' ? to === '/' : to === path || to.startsWith(`${path}/`)
  })
  if (!here.length) return null
  return here.some((i) => i.severity === 'error') ? 'down' : 'warn'
}

/** The worse of several looks. */
export const worstLook = (looks: ('down' | 'warn' | null)[]): 'down' | 'warn' | null =>
  looks.includes('down') ? 'down' : looks.includes('warn') ? 'warn' : null

/** The folded Today card an incident's rule is about: a card that stays folded while its row says it. */
const RULE_CARD: Record<string, FoldedCardId> = {
  disk_space: 'nas',
  smart: 'nas',
  container_health: 'services',
  backup_missing: 'backups',
  storage_box: 'backups',
  outside_services: 'outside',
  adguard: 'dns',
}

/** The folded cards an open incident already speaks for (plan.md M38: one badge per fact). */
export const coveredCards = (open: Incident[]): Set<FoldedCardId> =>
  new Set(open.map((i) => RULE_CARD[i.rule]).filter((id): id is FoldedCardId => id !== undefined))

/** Dismisses an open incident until it resolves (off the rows, dots, briefing and /status), or brings it back. */
export const setDismissed = (key: string, dismissed: boolean) =>
  sendJson<{ ok: boolean }>('POST', `/api/alerts/incidents/${dismissed ? 'dismiss' : 'undismiss'}`, { key })
