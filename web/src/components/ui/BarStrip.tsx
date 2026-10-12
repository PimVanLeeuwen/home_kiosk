import { useId } from 'react'
import { TONE_COLOR, type Tone } from './tones'

interface Props {
  values: number[]
  label: string
  /** The colour of the ordinary bars; the last one is lit. */
  tone?: Tone
  /** Bars to pick out, by index (for example a slow night in amber). */
  marks?: Record<number, Tone>
  /** Words under the strip: left, under a marked bar, right. */
  start?: string
  end?: string
  markLabel?: string
}

const W = 300
const H = 46

/** A row of bars, oldest left, with the newest lit: 30 nights of backups and the like. */
export function BarStrip({ values, label, tone = 'up', marks = {}, start, end, markLabel }: Props) {
  const id = useId()
  if (values.length === 0) return null
  const top = Math.max(...values) || 1
  const bw = W / values.length
  const color = TONE_COLOR[tone]
  const marked = Object.keys(marks).map(Number)
  return (
    <svg role="img" aria-label={label} viewBox={`0 0 ${W} ${H + 12}`} className="block w-full overflow-visible">
      <defs>
        <linearGradient id={`${id}-bar`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor={color} stopOpacity="0.5" />
          <stop offset="1" stopColor={color} stopOpacity="0.1" />
        </linearGradient>
        <filter id={`${id}-lit`} x="-60%" y="-60%" width="220%" height="220%">
          <feGaussianBlur stdDeviation="2" result="b" />
          <feMerge>
            <feMergeNode in="b" />
            <feMergeNode in="SourceGraphic" />
          </feMerge>
        </filter>
      </defs>
      {values.map((v, i) => {
        const h = Math.max(2, (v / top) * (H - 4))
        const last = i === values.length - 1
        const fill = marks[i] ? TONE_COLOR[marks[i]] : last ? color : `url(#${id}-bar)`
        return (
          <rect
            key={i}
            x={(i * bw + Math.min(1.3, bw * 0.15)).toFixed(1)}
            y={(H - h).toFixed(1)}
            width={Math.max(1, bw - Math.min(2.6, bw * 0.3)).toFixed(1)}
            height={h.toFixed(1)}
            rx="2"
            fill={fill}
            filter={last ? `url(#${id}-lit)` : undefined}
          />
        )
      })}
      {start && (
        <text x="0" y={H + 11} fontSize="9" fill="var(--color-faint)">
          {start}
        </text>
      )}
      {markLabel && marked.length > 0 && (
        <text x={(marked[0] * bw + bw / 2).toFixed(1)} y={H + 11} fontSize="9" fill={TONE_COLOR[marks[marked[0]]]} textAnchor="middle">
          {markLabel}
        </text>
      )}
      {end && (
        <text x={W} y={H + 11} fontSize="9" fill="var(--color-faint)" textAnchor="end">
          {end}
        </text>
      )}
    </svg>
  )
}
