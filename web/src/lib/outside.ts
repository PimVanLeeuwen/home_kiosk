import type { OutsideIncident, OutsideService, OutsideState } from './types'

export const STATE_LABEL: Record<OutsideState, string> = {
  ok: 'Operational',
  maintenance: 'Maintenance',
  degraded: 'Degraded',
  outage: 'Outage',
  unknown: 'Unknown',
}

/** Text colour per state; maintenance is planned, so it stays calm. */
export const STATE_TEXT: Record<OutsideState, string> = {
  ok: 'text-up',
  maintenance: 'text-accent-fg',
  degraded: 'text-warn',
  outage: 'text-down',
  unknown: 'text-faint',
}

const RANK: Record<OutsideState, number> = { outage: 0, degraded: 1, maintenance: 2, unknown: 3, ok: 4 }

/** Services with a problem (degraded or outage), worst first. */
export function troubled(services: OutsideService[]): OutsideService[] {
  return services
    .filter((s) => s.state === 'degraded' || s.state === 'outage')
    .sort((a, b) => RANK[a.state] - RANK[b.state])
}

/** "for 24 min", "for 3 h", "for 12 days": how long an incident has run. */
export function runningFor(startedAt: string | null, now = new Date()): string | null {
  if (!startedAt) return null
  const minutes = Math.max(0, Math.round((now.getTime() - new Date(startedAt).getTime()) / 60_000))
  if (minutes < 60) return `for ${minutes} min`
  if (minutes < 48 * 60) return `for ${Math.floor(minutes / 60)} h`
  return `for ${Math.floor(minutes / 1440)} days`
}

/** The status page's word, capitalised: "investigating" → "Investigating". */
export function statusWord(status: string): string {
  const word = status.replace(/_/g, ' ')
  return word.charAt(0).toUpperCase() + word.slice(1)
}

/** The incident to lead with for a service in trouble; one that only its
 * components report (no incident posted yet) gets a stand-in. */
export function headline(s: OutsideService): OutsideIncident {
  return (
    s.incidents.find((i) => i.impact !== 'maintenance') ?? {
      title: 'a problem on the status page',
      impact: s.state === 'outage' ? 'outage' : 'degraded',
      status: '',
      started_at: null,
      url: s.url,
      updates: [],
    }
  )
}
