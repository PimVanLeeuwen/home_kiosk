import { useId } from 'react'
import { TONE_COLOR, type Tone } from './tones'

interface Props {
  values: number[]
  label: string
  tone?: Tone
  /** Height in px; the width follows the container. */
  height?: number
  className?: string
}

const W = 600
const H = 120

/** An area chart with a glowing line, meant to run edge to edge in a card. */
export function GlowArea({ values, label, tone = 'accent', height = 118, className }: Props) {
  const id = useId()
  if (values.length < 2) return null
  const min = Math.min(...values)
  const span = Math.max(...values) - min || 1
  const pts = values
    .map((v, i) => `${((i / (values.length - 1)) * W).toFixed(1)},${(12 + (1 - (v - min) / span) * (H - 26)).toFixed(1)}`)
    .join(' ')
  const color = TONE_COLOR[tone]
  return (
    <svg
      role="img"
      aria-label={label}
      viewBox={`0 0 ${W} ${H}`}
      preserveAspectRatio="none"
      height={height}
      className={className ?? 'block w-full'}
    >
      <defs>
        <linearGradient id={`${id}-fill`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor={color} stopOpacity="0.3" />
          <stop offset="1" stopColor={color} stopOpacity="0" />
        </linearGradient>
      </defs>
      {[1 / 3, 2 / 3].map((f) => (
        <line key={f} x1="0" x2={W} y1={H * f} y2={H * f} stroke="rgb(255 255 255 / 0.04)" vectorEffect="non-scaling-stroke" />
      ))}
      <polygon points={`0,${H} ${pts} ${W},${H}`} fill={`url(#${id}-fill)`} />
      <polyline
        points={pts}
        fill="none"
        stroke={color}
        strokeWidth="2"
        strokeLinejoin="round"
        vectorEffect="non-scaling-stroke"
        style={{ filter: `drop-shadow(0 0 4px ${color})` }}
      />
    </svg>
  )
}
