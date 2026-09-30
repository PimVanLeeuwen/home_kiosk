import { ExternalLink, TriangleAlert } from 'lucide-react'
import { tileColour } from '../lib/monogram'
import { statsSummary } from '../lib/stats'
import type { Service } from '../lib/types'
import { StatusDot } from './StatusDot'

interface Props {
  service: Service
  href: string
  /** Tile letters and position in the catalog; see uniqueMonograms and tileColour. */
  label: string
  index: number
}

export function ServiceTile({ service, href, label, index }: Props) {
  const colour = tileColour(index)
  // Live stats replace the description when the widget delivers them. Two fit
  // on a tile; the tooltip has them all.
  const stats = service.stats?.length ? service.stats : null
  const detail = stats ? statsSummary(stats, 2) : service.description
  const fullDetail = stats ? statsSummary(stats) : service.description

  return (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      className="flex items-center gap-3 rounded-[10px] border border-transparent bg-raised px-3 py-2.75 transition-colors hover:border-line"
    >
      <span
        aria-hidden="true"
        className="grid size-[30px] shrink-0 place-items-center rounded-lg text-xs font-bold"
        style={{ backgroundColor: colour.bg, color: colour.fg }}
      >
        {label}
      </span>
      <span className="min-w-0 flex-1">
        <span className="block truncate text-[13.5px] font-medium">{service.name}</span>
        {detail && (
          <span className="block truncate text-[11.5px] text-muted" title={fullDetail}>
            {detail}
          </span>
        )}
      </span>
      {service.stats_error && (
        <span title={`Stats: ${service.stats_error}`} className="text-warn">
          <TriangleAlert aria-hidden="true" className="size-3.5" />
          <span className="sr-only">Stats unavailable: {service.stats_error}</span>
        </span>
      )}
      {service.url ? (
        // A link has no container to report on.
        <ExternalLink aria-hidden="true" className="size-3.5 shrink-0 text-faint" />
      ) : (
        <StatusDot status={service.status} />
      )}
      <span className="sr-only">(opens in a new tab)</span>
    </a>
  )
}
