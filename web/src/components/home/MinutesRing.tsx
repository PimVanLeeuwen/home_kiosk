import { Ring } from '../ui/Ring'

/** Minutes in a ring that empties over the last hour: to the next event, to the train. */
export function MinutesRing({ minutes, color, label, className }: { minutes: number; color: string; label: string; className: string }) {
  return (
    <Ring role="img" aria-label={`${minutes} ${label}`} className={className} box={64} r={26} stroke={4.5} glow={3} color={color} fraction={minutes / 60}>
      <text x="32" y="33" textAnchor="middle" fontSize="16" fontWeight="600" fill="var(--color-fg)">
        {minutes}
      </text>
      <text x="32" y="44" textAnchor="middle" fontSize="6.5" fill="var(--color-muted)">
        {label}
      </text>
    </Ring>
  )
}
