import { TONE_COLOR, type Tone } from './tones'

interface Props {
  values: number[]
  label: string
  tone?: Tone
  /** The scale: from `min` (else the lowest value) to at least `floor`, so a near-idle line stays flat. */
  min?: number
  floor?: number
}

/** A thin glowing line for a glass tile: the shape of the last hours, no axes. */
export function MiniSparkline({ values, label, tone = 'accent', min: low, floor }: Props) {
  if (values.length < 2) return null
  const min = low ?? Math.min(...values)
  const span = Math.max(...values, floor ?? -Infinity) - min || 1
  const points = values
    .map((v, i) => `${((i / (values.length - 1)) * 60).toFixed(1)},${(17 - ((v - min) / span) * 13).toFixed(1)}`)
    .join(' ')
  const color = TONE_COLOR[tone]
  return (
    <svg role="img" aria-label={label} viewBox="0 0 60 20" preserveAspectRatio="none" className="block h-5 w-full overflow-visible motion-safe:animate-reveal">
      <polyline
        points={points}
        fill="none"
        stroke={color}
        strokeWidth="1.4"
        strokeLinejoin="round"
        strokeLinecap="round"
        vectorEffect="non-scaling-stroke"
        style={{ filter: `drop-shadow(0 0 2px ${color})` }}
      />
    </svg>
  )
}
