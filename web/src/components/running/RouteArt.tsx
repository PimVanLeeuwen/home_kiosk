import { useId } from 'react'
import { cn } from '../../lib/cn'
import { paceColour, paceRange, project, type RoutePoint } from '../../lib/running'

interface Props {
  points: RoutePoint[]
  width?: number
  height?: number
  /** Room round the route, in the drawing's units. */
  pad?: number
  /** Thinner, without the end marks: a route in miniature. */
  mini?: boolean
  label?: string
  className?: string
}

/**
 * A run's route as light (plan.md M28, A): every stretch coloured by its pace
 * against the run's own range, cool blue when easy to white when fastest,
 * over a soft glow of the whole line. Where you started a small dot, where you
 * finished a lit point. Drawn on its own: no map from outside.
 */
export function RouteArt({ points, width = 640, height = 380, pad = 40, mini = false, label, className }: Props) {
  const id = useId()
  if (points.length < 2) return null
  const xy = project(points, width, height, pad)
  const [slowest, fastest] = paceRange(points)
  const line = xy.map(([x, y], i) => `${i ? 'L' : 'M'}${x.toFixed(1)} ${y.toFixed(1)}`).join(' ')
  const stroke = mini ? 2 : 3.2
  const [sx, sy] = xy[0]
  const [ex, ey] = xy[xy.length - 1]

  return (
    <svg
      viewBox={`0 0 ${width} ${height}`}
      preserveAspectRatio="xMidYMid meet"
      role={label ? 'img' : undefined}
      aria-label={label}
      aria-hidden={label ? undefined : true}
      className={cn('block overflow-visible motion-safe:animate-reveal', className)}
    >
      <defs>
        <filter id={`${id}glow`} x="-20%" y="-20%" width="140%" height="140%">
          <feGaussianBlur stdDeviation={mini ? 2 : 7} />
        </filter>
      </defs>
      <path d={line} fill="none" stroke="#f2a65a" strokeOpacity={mini ? 0.35 : 0.28} strokeWidth={stroke * 4} strokeLinecap="round" strokeLinejoin="round" filter={`url(#${id}glow)`} />
      {xy.slice(1).map(([x, y], i) => (
        <line
          key={i}
          x1={xy[i][0]}
          y1={xy[i][1]}
          x2={x}
          y2={y}
          stroke={paceColour(points[i + 1][2], slowest, fastest)}
          strokeWidth={stroke}
          strokeLinecap="round"
        />
      ))}
      {!mini && (
        <>
          <circle cx={sx} cy={sy} r="5" fill="#0b0b10" stroke="#fff" strokeWidth="2" />
          <circle cx={ex} cy={ey} r="14" fill="#fff4de" opacity="0.18" />
          <circle cx={ex} cy={ey} r="6.5" fill="#fff4de" />
        </>
      )}
    </svg>
  )
}
