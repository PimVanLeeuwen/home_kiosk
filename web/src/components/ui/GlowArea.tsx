import { useId } from 'react'
import { TONE_COLOR, type Tone } from './tones'

interface Props {
  values: number[]
  label: string
  tone?: Tone
  /** A colour of its own instead of a tone (e.g. a cool blue for temperatures). */
  color?: string
  /** Height in px; the width follows the container. */
  height?: number
  /** A fixed scale, e.g. 0 to 100 for percentages; otherwise the series' own range. */
  min?: number
  max?: number
  /** A glowing dot on the highest point. */
  peak?: boolean
  /** A thin second line on the same scale, such as upload under download. */
  secondary?: number[]
  className?: string
}

const W = 600
const H = 120

/** An area chart with a glowing line, meant to run edge to edge in a card. */
export function GlowArea({ values, label, tone = 'accent', color, height = 118, min, max, peak, secondary, className }: Props) {
  const id = useId()
  if (values.length < 2) return null
  const all = secondary ? [...values, ...secondary] : values
  const low = min ?? Math.min(...all)
  const span = (max ?? Math.max(...all)) - low || 1
  const point = (v: number, i: number, n: number) =>
    [(i / (n - 1)) * W, 12 + (1 - Math.min(1, Math.max(0, (v - low) / span))) * (H - 26)] as const
  const toPoints = (series: number[]) =>
    series.map((v, i) => point(v, i, series.length).map((n) => n.toFixed(1)).join(',')).join(' ')
  const pts = toPoints(values)
  const stroke = color ?? TONE_COLOR[tone]
  const top = values.indexOf(Math.max(...values))
  const [px, py] = point(values[top], top, values.length)
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
          <stop offset="0" stopColor={stroke} stopOpacity="0.3" />
          <stop offset="1" stopColor={stroke} stopOpacity="0" />
        </linearGradient>
      </defs>
      {[1 / 3, 2 / 3].map((f) => (
        <line key={f} x1="0" x2={W} y1={H * f} y2={H * f} stroke="rgb(255 255 255 / 0.04)" vectorEffect="non-scaling-stroke" />
      ))}
      <polygon points={`0,${H} ${pts} ${W},${H}`} fill={`url(#${id}-fill)`} />
      <polyline
        points={pts}
        fill="none"
        stroke={stroke}
        strokeWidth="2"
        strokeLinejoin="round"
        vectorEffect="non-scaling-stroke"
        style={{ filter: `drop-shadow(0 0 4px ${stroke})` }}
      />
      {secondary && secondary.length > 1 && (
        <polyline
          data-testid="secondary"
          points={toPoints(secondary)}
          fill="none"
          stroke="var(--color-muted)"
          strokeOpacity="0.7"
          strokeWidth="1"
          vectorEffect="non-scaling-stroke"
        />
      )}
      {peak && (
        // An ellipse that stays round in a chart stretched to its container is not
        // worth it at this size: a short vertical tick carries the glow instead.
        <line
          data-testid="peak"
          x1={px.toFixed(1)}
          x2={px.toFixed(1)}
          y1={(py - 0.5).toFixed(1)}
          y2={(py + 0.5).toFixed(1)}
          stroke={stroke}
          strokeWidth="6"
          strokeLinecap="round"
          vectorEffect="non-scaling-stroke"
          style={{ filter: `drop-shadow(0 0 3px ${stroke})` }}
        />
      )}
    </svg>
  )
}
