import type { ReactNode, SVGProps } from 'react'

interface Props extends Omit<SVGProps<SVGSVGElement>, 'viewBox' | 'fill' | 'stroke'> {
  /** How much of the ring is drawn, 0 to 1, clockwise from the top. */
  fraction: number
  /** Where the arc begins, as a fraction of the ring after the top (a time span on a clock). */
  start?: number
  color: string
  /** The square the ring is drawn in, in SVG units; radius and stroke are in the same units. */
  box: number
  r: number
  stroke: number
  /** The unfilled part; the theme's track by default. */
  track?: string
  /** The inside of the ring (a ring on a picture needs one). */
  fill?: string
  /** The glow around the arc, in SVG units; none at 0. */
  glow?: number
  cap?: 'round' | 'butt'
  /** Text or marks drawn over the ring, in the same units. */
  children?: ReactNode
}

/**
 * The hub's ring: a track and an arc in a colour that sweeps in when it first shows.
 * RingMeter, the minutes to go, reading progress and quiet hours all draw with it.
 */
export function Ring({ fraction, start = 0, color, box, r, stroke, track = 'var(--color-track)', fill = 'none', glow = 0, cap = 'round', children, ...svg }: Props) {
  const c = 2 * Math.PI * r
  const mid = box / 2
  const drawn = Math.min(1, Math.max(0, fraction))
  return (
    <svg viewBox={`0 0 ${box} ${box}`} {...svg}>
      <circle cx={mid} cy={mid} r={r} fill={fill} stroke={track} strokeWidth={stroke} />
      {drawn > 0 && (
        <circle
          data-arc
          cx={mid}
          cy={mid}
          r={r}
          fill="none"
          stroke={color}
          strokeWidth={stroke}
          strokeLinecap={cap}
          className="motion-safe:animate-sweep"
          strokeDasharray={`${(c * drawn).toFixed(2)} ${c.toFixed(2)}`}
          strokeDashoffset={start ? (-start * c).toFixed(2) : undefined}
          transform={`rotate(-90 ${mid} ${mid})`}
          style={glow ? { filter: `drop-shadow(0 0 ${glow}px ${color})` } : undefined}
        />
      )}
      {children}
    </svg>
  )
}
