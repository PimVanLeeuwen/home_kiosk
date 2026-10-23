import { useId } from 'react'
import { rainSummary, WET_MM, type RainPoint } from '../../lib/rain'

interface Props {
  points: RainPoint[]
  /** In the middle: the temperature, rounded. */
  temperature: number | null
}

/** Rain this heavy fills a segment; anything above looks the same. */
const TOP_MM = 3
const R = 38

const polar = (r: number, deg: number) => [50 + r * Math.sin((deg * Math.PI) / 180), 50 - r * Math.cos((deg * Math.PI) / 180)]

/**
 * The next two hours of rain as a ring around the temperature, as on the Now
 * panel: starting at the top at now and going round clockwise, one segment per
 * five minutes, longer as the rain gets heavier.
 */
export function RainRing({ points, temperature }: Props) {
  const id = useId()
  const step = points.length ? 360 / points.length : 0
  const gap = Math.min(1.6, step * 0.12)
  return (
    <svg role="img" aria-label={rainSummary(points)} viewBox="0 0 100 100" className="block w-full">
      <defs>
        <radialGradient id={`${id}-rain`} cx="50" cy="50" r="52" gradientUnits="userSpaceOnUse">
          <stop offset="0.7" stopColor="var(--color-accent)" />
          <stop offset="1" stopColor="var(--color-data-lavender)" />
        </radialGradient>
        <radialGradient id={`${id}-core`}>
          <stop offset="0" stopColor="color-mix(in srgb, var(--color-violet) 20%, transparent)" />
          <stop offset="1" stopColor="color-mix(in srgb, var(--color-violet) 0%, transparent)" />
        </radialGradient>
      </defs>
      <circle cx="50" cy="50" r="33" fill={`url(#${id}-core)`} />
      {points.map((p, i) => {
        const wet = p.mm_per_hour >= WET_MM
        const len = wet ? 3 + (Math.sqrt(Math.min(p.mm_per_hour, TOP_MM)) / Math.sqrt(TOP_MM)) * 8 : 1.4
        const a0 = i * step + gap
        const a1 = (i + 1) * step - gap
        const [x0, y0] = polar(R, a0)
        const [x1, y1] = polar(R, a1)
        const [x2, y2] = polar(R + len, a1)
        const [x3, y3] = polar(R + len, a0)
        const f = (n: number) => n.toFixed(2)
        return (
          <path
            key={p.at}
            data-wet={wet || undefined}
            d={`M${f(x0)} ${f(y0)} A${R} ${R} 0 0 1 ${f(x1)} ${f(y1)} L${f(x2)} ${f(y2)} A${R + len} ${R + len} 0 0 0 ${f(x3)} ${f(y3)} Z`}
            fill={wet ? `url(#${id}-rain)` : 'rgb(255 255 255 / 0.12)'}
          />
        )
      })}
      {/* Now, at the top. */}
      <path d="M50 6 L50 10.5" stroke="#fff" strokeWidth="0.9" strokeLinecap="round" />
      {temperature != null && (
        <text x="50" y="56" textAnchor="middle" fontSize="19" fontWeight="600" fill="var(--color-fg)" letterSpacing="-0.5">
          {Math.round(temperature)}°
        </text>
      )}
    </svg>
  )
}
