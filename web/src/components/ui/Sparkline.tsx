import { useId } from 'react'
import { cn } from '../../lib/cn'
import { TONE_COLOR, type Tone } from './tones'

interface Props {
  values: number[]
  label: string
  tone?: Tone
  /** The scale: from `min` (else the lowest value) to at least `floor`, so a near-idle line stays flat. */
  min?: number
  floor?: number
  /** For layout only (its height and place in a cell). */
  className?: string
}

const W = 300
const H = 44

/**
 * A fine line under a cell's figure, with a soft wash below it fading to nothing: the shape of
 * the last hours, no axes. MiniSparkline is its smaller kin for a glass tile.
 */
export function Sparkline({ values, label, tone = 'accent', min: low, floor, className }: Props) {
  const id = useId()
  if (values.length < 2) return null
  const min = low ?? Math.min(...values)
  const span = Math.max(...values, floor ?? -Infinity) - min || 1
  const line = values
    .map((v, i) => `${i ? 'L' : 'M'}${((i / (values.length - 1)) * W).toFixed(1)},${(H - 2 - ((v - min) / span) * (H - 6)).toFixed(1)}`)
    .join(' ')
  const color = TONE_COLOR[tone]
  return (
    <svg
      role="img"
      aria-label={label}
      viewBox={`0 0 ${W} ${H}`}
      preserveAspectRatio="none"
      className={cn('block h-11 w-full overflow-visible motion-safe:animate-reveal', className)}
    >
      <defs>
        <linearGradient id={id} x1="0" x2="0" y1="0" y2="1">
          <stop offset="0" stopColor={color} stopOpacity="0.22" />
          <stop offset="1" stopColor={color} stopOpacity="0" />
        </linearGradient>
      </defs>
      <path d={`${line} L${W},${H} L0,${H} Z`} fill={`url(#${id})`} />
      <path d={line} fill="none" stroke={color} strokeWidth="1.5" strokeLinejoin="round" vectorEffect="non-scaling-stroke" />
    </svg>
  )
}
