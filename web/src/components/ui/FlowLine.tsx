import { cn } from '../../lib/cn'

interface Props {
  from: string
  to: string
  /** A light runs along the line while the route works; a broken route is red and still. */
  ok?: boolean
}

const chip = 'rounded-full border border-glass-line bg-glass px-[9px] py-[3px] whitespace-nowrap text-muted'

/** A route between two places, such as the NAS to Hetzner, with a slow light along it. */
export function FlowLine({ from, to, ok = true }: Props) {
  return (
    <div className="flex items-center gap-2.5 text-caption" aria-label={`${from} to ${to}`} role="img">
      <span className={chip}>{from}</span>
      <span className={cn('relative h-0.5 flex-1 overflow-hidden rounded-full', ok ? 'bg-up/22' : 'bg-down/35')}>
        {ok && (
          <i className="absolute -top-px h-1 w-[28%] rounded-full bg-linear-to-r from-transparent via-[var(--color-data-mint)] to-transparent motion-safe:animate-flow motion-reduce:left-[36%]" />
        )}
      </span>
      <span className={chip}>{to}</span>
    </div>
  )
}
