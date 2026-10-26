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
  /** Which marked bar the label goes under; the first one by default. */
  markAt?: number
  /** Height of the bars in px; they stretch to the container's width. */
  height?: number
}

const W = 300
const H = 46

/** A row of bars, oldest left, with the newest lit: 30 nights of backups and the like. */
export function BarStrip({ values, label, tone = 'up', marks = {}, start, end, markLabel, markAt, height = 56 }: Props) {
  const id = useId()
  if (values.length === 0) return null
  const top = Math.max(...values) || 1
  const bw = W / values.length
  const color = TONE_COLOR[tone]
  const labelled = markAt ?? Object.keys(marks).map(Number)[0]
  // A label under the newest bar would sit on the end words: they share one line instead.
  const atEnd = labelled === values.length - 1 && !!end && !!markLabel && !!marks[labelled]
  const labelStyle = (t: Tone | undefined) => ({ color: t ? TONE_COLOR[t] : 'var(--color-faint)' })
  return (
    <div>
      <svg
        role="img"
        aria-label={label}
        viewBox={`0 0 ${W} ${H}`}
        preserveAspectRatio="none"
        height={height}
        className="block w-full overflow-visible"
      >
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
              className="origin-bottom [transform-box:fill-box] motion-safe:animate-grow"
              style={{ animationDelay: `${Math.min(i * 14, 420)}ms` }}
            />
          )
        })}
      </svg>
      {/* Words in HTML rather than SVG text, so they keep their size however wide the strip runs. */}
      {(start || end || markLabel) && (
        <div className="relative mt-1 flex h-4 justify-between text-label" aria-hidden="true">
          <span style={labelStyle(undefined)}>{start}</span>
          {markLabel && labelled != null && marks[labelled] && !atEnd && (
            <span
              data-tone={marks[labelled]}
              className="absolute -translate-x-1/2 whitespace-nowrap"
              style={{ ...labelStyle(marks[labelled]), left: `${((labelled + 0.5) / values.length) * 100}%` }}
            >
              {markLabel}
            </span>
          )}
          <span data-tone={atEnd ? marks[labelled] : undefined} style={labelStyle(atEnd ? marks[labelled] : undefined)}>
            {atEnd ? `${end}: ${markLabel}` : end}
          </span>
        </div>
      )}
    </div>
  )
}
