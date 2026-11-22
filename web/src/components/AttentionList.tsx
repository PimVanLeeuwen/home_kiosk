import { lasted, incidentPath } from '../lib/incidents'
import { NAV_ITEMS } from '../lib/navigation'
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

/** One row per open incident, worst first (plan.md M38: attention first), each with the way to its page. */
export function AttentionList({ incidents, here, now = new Date() }: Props) {
  if (!incidents.length) return null
  return (
    <ul aria-label="Needs a look" className="mb-5 grid gap-2.5">
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
            />
          </li>
        )
      })}
    </ul>
  )
}
