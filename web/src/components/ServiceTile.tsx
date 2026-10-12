import { ExternalLink, TriangleAlert } from 'lucide-react'
import { cn } from '../lib/cn'
import { statParts, statsSummary } from '../lib/stats'
import type { Service } from '../lib/types'
import { ServiceIcon } from './ServiceIcon'
import { StatusDot } from './StatusDot'

interface Props {
  service: Service
  href: string
  /** Tile letters and position in the catalog; see uniqueMonograms and tileColour. */
  label: string
  index: number
}

export function ServiceTile({ service, href, label, index }: Props) {
  // Live stats replace the description when the widget delivers them. Two fit
  // on a tile; the tooltip has them all.
  const stats = service.stats?.length ? service.stats : null
  const fullDetail = stats ? statsSummary(stats) : service.description
  const trouble = ['down', 'missing'].includes(service.status) ? 'down' : service.status === 'unhealthy' ? 'warn' : null

  return (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      data-trouble={trouble ?? undefined}
      className={cn(
        'flex items-center gap-3 rounded-[12px] border px-3 py-2.5 transition-colors',
        trouble === 'down'
          ? 'border-down/40 bg-linear-to-br from-down/12 to-down/[0.03] hover:border-down/60'
          : trouble === 'warn'
            ? 'border-warn/35 bg-linear-to-br from-warn/11 to-warn/[0.03] hover:border-warn/55'
            : 'border-glass-line bg-glass hover:border-line',
      )}
    >
      <ServiceIcon icon={service.icon} label={label} index={index} />
      <span className="min-w-0 flex-1">
        <span className="block truncate text-[13.5px] font-medium">{service.name}</span>
        {stats ? (
          // Two chips fit; the tooltip has them all. The separators keep the line readable aloud.
          <span className="mt-0.5 flex min-w-0 gap-1 overflow-hidden" title={fullDetail}>
            {stats.slice(0, 2).map((st, i) => {
              const [figure, word] = statParts(st)
              return (
                <span key={st.label} className="contents">
                  {i > 0 && <span className="sr-only"> · </span>}
                  <span className="shrink-0 rounded-[6px] border border-glass-line bg-white/5 px-1.5 text-[11px] whitespace-nowrap text-muted">
                    <b className="font-semibold text-fg">{figure}</b> {word}
                  </span>
                </span>
              )
            })}
          </span>
        ) : (
          service.description && (
            <span className={cn('block truncate text-[11.5px]', trouble === 'down' ? 'text-down' : 'text-muted')} title={fullDetail}>
              {trouble === 'down' ? 'Stopped' : service.description}
            </span>
          )
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
