import { Sparkles } from 'lucide-react'
import { formatTime } from '../../lib/format'
import type { Briefing } from '../../lib/types'
import { Card } from '../ui/Card'
import { StaleNote } from '../ui/states'

const weekday = new Intl.DateTimeFormat('en-GB', { weekday: 'long' })

/** The morning digest on Home until 09:00, as on the Now panel's Briefing screen (plan.md M26). */
export function BriefingCard({ data }: { data: Briefing | undefined }) {
  if (!data) return null
  return (
    <Card
      title={`Briefing · ${weekday.format(new Date(`${data.date}T12:00`))}`}
      actions={
        <span className="inline-flex items-center gap-1.5 text-caption text-muted">
          <Sparkles aria-hidden="true" className="size-3.5 text-accent-fg" />
          written by Claude
        </span>
      }
    >
      <p className="text-heading font-semibold tracking-tight">{data.line}</p>
      <ul className="mt-4 grid gap-2 sm:grid-cols-2">
        {data.facts.map((fact) => (
          <li key={fact} className="flex items-center gap-2.5 rounded-[10px] border border-line-soft bg-white/[0.02] px-3 py-2 text-small">
            <span aria-hidden="true" className="size-1.5 shrink-0 rounded-full bg-accent-line" />
            {fact}
          </li>
        ))}
      </ul>
      <p className="mt-3 text-caption text-faint">As of {formatTime(data.as_of)}</p>
      {data.stale && <StaleNote />}
    </Card>
  )
}
