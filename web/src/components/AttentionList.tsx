import { useState } from 'react'
import { ApiError } from '../lib/api'
import { incidentPath, lasted, setDismissed } from '../lib/incidents'
import { NAV_ITEMS } from '../lib/navigation'
import { useOpenIncidents } from '../lib/openIncidents'
import { PATHS } from '../lib/paths'
import type { Incident } from '../lib/types'
import { AttentionRow } from './ui/AttentionRow'

const since = new Intl.DateTimeFormat('en-GB', { weekday: 'short', day: 'numeric', month: 'short' })

/** The page's name for an action: "Docker", "Desk panels"; Alerts for a rule without a page. */
function pageLabel(path: string): string {
  if (path.startsWith(`${PATHS.settings}/`)) return 'Settings'
  return NAV_ITEMS.find((item) => item.to === path)?.label ?? 'Alerts'
}

interface Props {
  incidents: Incident[]
  /** The page this list is on: an incident about it gets no link to itself. */
  here: string
  now?: Date
}

/**
 * One row per open incident, worst first (plan.md M38: attention first), each with the way to
 * its page and a Dismiss until it resolves; the last one dismissed can be undone right here.
 */
export function AttentionList({ incidents, here, now = new Date() }: Props) {
  const { reload } = useOpenIncidents()
  const [last, setLast] = useState<{ key: string; title: string }>()
  const [error, setError] = useState<string>()

  async function dismiss({ key, title }: { key: string; title: string }, dismissed: boolean) {
    setError(undefined)
    try {
      await setDismissed(key, dismissed)
      setLast(dismissed ? { key, title } : undefined)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'That did not work; try again.')
    }
    reload()
  }

  if (!incidents.length && !last && !error) return null
  return (
    <div className="mb-5 grid gap-2.5">
      {incidents.length > 0 && (
        <ul aria-label="Needs a look" className="grid gap-2.5">
          {incidents.map((incident) => {
            const to = incidentPath(incident)
            const firstLine = incident.body.split('\n')[0]
            const opened = new Date(incident.opened_at)
            return (
              <li key={incident.key}>
                <AttentionRow
                  tone={incident.severity === 'error' ? 'down' : 'warn'}
                  title={incident.title}
                  detail={`${firstLine ? `${firstLine} · ` : ''}since ${since.format(opened)}, ${lasted(now.getTime() - opened.getTime())}`}
                  action={to === here ? undefined : { to, label: pageLabel(to) }}
                  onDismiss={() => dismiss(incident, true)}
                />
              </li>
            )
          })}
        </ul>
      )}
      <p role="status" className="text-small text-muted empty:hidden">
        {error && <span className="text-down">{error}</span>}
        {!error && last && (
          <>
            Dismissed “{last.title}” until it resolves.{' '}
            <button
              type="button"
              onClick={() => dismiss(last, false)}
              className="hit font-medium text-accent-fg hover:underline"
            >
              Undo
            </button>
          </>
        )}
      </p>
    </div>
  )
}
