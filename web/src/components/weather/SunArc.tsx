import { useId } from 'react'
import { formatTime } from '../../lib/format'

interface Props {
  sunrise: string
  sunset: string
  now: Date
}

/** The sun's day as an arc from sunrise to sunset, with the sun where it is now (none at night). */
export function SunArc({ sunrise, sunset, now }: Props) {
  const id = useId()
  const rise = new Date(sunrise).getTime()
  const set = new Date(sunset).getTime()
  const f = (now.getTime() - rise) / (set - rise)
  const up = set > rise && f >= 0 && f <= 1
  const x = 6 + f * 88
  const y = 34 - Math.sin(f * Math.PI) * 26
  const label = up
    ? `Sun up from ${formatTime(sunrise)} to ${formatTime(sunset)}`
    : now.getTime() < rise
      ? `Sunrise at ${formatTime(sunrise)}`
      : `The sun set at ${formatTime(sunset)}`
  return (
    <svg role="img" aria-label={label} viewBox="0 0 100 36" className="block w-full max-w-[260px] overflow-visible">
      <defs>
        <linearGradient id={`${id}-arc`} x1="0" x2="1">
          <stop offset="0" stopColor="rgb(224 162 59 / 0.15)" />
          <stop offset="0.5" stopColor="rgb(224 162 59 / 0.55)" />
          <stop offset="1" stopColor="rgb(229 100 106 / 0.2)" />
        </linearGradient>
      </defs>
      <line x1="2" x2="98" y1="34" y2="34" stroke="rgb(255 255 255 / 0.08)" />
      <path d="M6 34 Q50 -18 94 34" fill="none" stroke={`url(#${id}-arc)`} strokeWidth="1.4" strokeDasharray="1.5 2" />
      {up && (
        <circle
          data-testid="sun"
          cx={x.toFixed(1)}
          cy={y.toFixed(1)}
          r="3"
          fill="#f2c45a"
          style={{ filter: 'drop-shadow(0 0 4px #f2c45a)' }}
        />
      )}
    </svg>
  )
}
