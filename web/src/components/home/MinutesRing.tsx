import { cn } from '../../lib/cn'
import { Ring } from '../ui/Ring'
import { SvgLabel } from '../ui/SvgLabel'

/** Minutes in a ring that empties over the last hour: to the next event, to the train. */
export function MinutesRing({ minutes, color, label, className }: { minutes: number; color: string; label: string; className: string }) {
  return (
    <div className={cn('relative', className)}>
      <Ring
        role="img"
        aria-label={`${minutes} ${label}`}
        className="block w-full"
        box={64}
        r={26}
        stroke={4.5}
        glow={3}
        color={color}
        fraction={minutes / 60}
      />
      <SvgLabel x={32} y={28} w={64} h={64} className="text-heading font-semibold">
        {minutes}
      </SvgLabel>
      {/* Two lines when it does not fit ("min to next"), inside the ring. */}
      <SvgLabel x={32} y={42} w={64} h={64} className="max-w-[62%] text-center text-label leading-tight whitespace-normal text-muted">
        {label}
      </SvgLabel>
    </div>
  )
}
