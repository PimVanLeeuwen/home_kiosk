import { tileColour } from '../lib/monogram'
import { serviceUrl } from '../lib/links'
import type { Service } from '../lib/types'
import { StatusDot } from './StatusDot'

interface Props {
  service: Service
  host: string
  /** Tile letters and position in the catalog; see uniqueMonograms and tileColour. */
  label: string
  index: number
}

export function ServiceTile({ service, host, label, index }: Props) {
  const colour = tileColour(index)

  return (
    <a
      href={serviceUrl(service, host)}
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
        {service.description && (
          <span className="block truncate text-[11.5px] text-muted">{service.description}</span>
        )}
      </span>
      <StatusDot status={service.status} />
      <span className="sr-only">(opens in a new tab)</span>
    </a>
  )
}
