import { TONE_COLOR, type Tone } from './tones'

interface Props {
  /** 0 to 100. */
  pct: number
  tone: Tone
  label: string
  /** Under the figure, small: what the ring measures. */
  caption?: string
}

const R = 42
const C = 2 * Math.PI * R

/** A full ring that fills clockwise from the top in its state's colour, the figure inside. */
export function RingMeter({ pct, tone, label, caption }: Props) {
  const value = Math.min(100, Math.max(0, pct))
  const color = TONE_COLOR[tone]
  return (
    <svg
      role="meter"
      aria-label={label}
      aria-valuenow={Math.round(value)}
      aria-valuemin={0}
      aria-valuemax={100}
      data-tone={tone}
      viewBox="0 0 100 100"
      className="block w-full"
    >
      <circle cx="50" cy="50" r={R} fill="none" stroke="rgb(255 255 255 / 0.07)" strokeWidth="7" />
      {value > 0 && (
        <circle
          cx="50"
          cy="50"
          r={R}
          fill="none"
          stroke={color}
          strokeWidth="7"
          strokeLinecap="round"
          className="motion-safe:animate-sweep"
          strokeDasharray={`${((C * value) / 100).toFixed(1)} ${C.toFixed(1)}`}
          transform="rotate(-90 50 50)"
          style={{ filter: `drop-shadow(0 0 4px ${color})` }}
        />
      )}
      <text x="50" y={caption ? 52 : 57} textAnchor="middle" fontSize="20" fontWeight="600" fill="var(--color-fg)">
        {Math.round(value)}%
      </text>
      {caption && (
        <text x="50" y="66" textAnchor="middle" fontSize="8.5" fill="var(--color-muted)">
          {caption}
        </text>
      )}
    </svg>
  )
}
