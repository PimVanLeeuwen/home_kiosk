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
