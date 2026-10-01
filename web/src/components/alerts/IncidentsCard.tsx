import { formatWhen } from '../../lib/format'
import type { Incident } from '../../lib/types'
import { useApi } from '../../lib/useApi'
import { Card } from '../home/Card'
import { SeverityPill } from './SeverityPill'

export function IncidentsCard() {
  const { data } = useApi<Incident[]>('/api/alerts/incidents', 60_000)
  const open = (data ?? []).filter((i) => !i.resolved_at)

  return (
    <Card title={`Open alerts${open.length ? ` (${open.length})` : ''}`}>
      {data && open.length === 0 && <p className="text-up">Nothing needs a look.</p>}
      <ul className="space-y-2.5">
        {open.map((i) => (
          <li key={i.key}>
            <p className="flex flex-wrap items-center gap-2">
              <SeverityPill severity={i.severity} />
              <span className="font-medium">{i.title}</span>
            </p>
            <p className="text-[12px] text-faint">
              {i.body ? `${i.body} · ` : ''}since {formatWhen(i.opened_at)}
            </p>
          </li>
        ))}
      </ul>
    </Card>
  )
}
