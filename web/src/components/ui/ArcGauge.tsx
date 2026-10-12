import { useId, type ReactNode } from 'react'
import { cn } from '../../lib/cn'

interface Props {
  /** 0 to 100. */
  pct: number
  /** Where an alert starts: a red mark on the scale, and the arc's end turns amber past it. */
  alertAt?: number
  label: string
  /** Below the figure: what is measured and how long it lasts. */
  children?: ReactNode
  /** The wrapper's size; centred at 72% of its container by default. */
  className?: string
}

const R = 40
const CX = 50
const CY = 52

/** A point on the half circle, `f` from 0 (left) to 1 (right). */
const at = (f: number, r = R) => [CX - r * Math.cos(f * Math.PI), CY - r * Math.sin(f * Math.PI)]
const arc = (f0: number, f1: number) => {
  const [x0, y0] = at(f0)
  const [x1, y1] = at(f1)
  return `M${x0.toFixed(2)} ${y0.toFixed(2)} A${R} ${R} 0 0 1 ${x1.toFixed(2)} ${y1.toFixed(2)}`
}

const TICKS = Array.from({ length: 21 }, (_, i) => {
  const [x0, y0] = at(i / 20, R + 6)
  const [x1, y1] = at(i / 20, R + (i % 5 ? 7.5 : 9))
  return { x0, y0, x1, y1, major: i % 5 === 0 }
})

/** An instrument-style half dial with ticks and a glowing arc, as on the House panel. */
export function ArcGauge({ pct, alertAt, label, children, className }: Props) {
  const id = useId()
  const value = Math.min(100, Math.max(0, pct))
  const over = alertAt != null && value >= alertAt
  const mark = alertAt != null ? at(alertAt / 100, R + 8) : null
  return (
    <div className={cn('text-center', className ?? 'mx-auto w-[72%] max-w-[270px]')}>
      <svg
        role="meter"
        aria-label={label}
        aria-valuenow={Math.round(value)}
        aria-valuemin={0}
        aria-valuemax={100}
        viewBox="0 2 100 56"
        className="block w-full overflow-visible"
      >
        <defs>
          <linearGradient id={`${id}-arc`} x1="0" x2="1">
            <stop offset="0" stopColor="#6f60ea" />
            <stop offset="0.75" stopColor="#b4a9ff" />
            <stop offset="1" stopColor={over ? 'var(--color-warn)' : '#cfc8ff'} />
          </linearGradient>
          <filter id={`${id}-glow`} x="-20%" y="-20%" width="140%" height="140%">
            <feGaussianBlur stdDeviation="1.6" result="b" />
            <feMerge>
              <feMergeNode in="b" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
        </defs>
        {TICKS.map((t, i) => (
          <line
            key={i}
            x1={t.x0.toFixed(2)}
            y1={t.y0.toFixed(2)}
            x2={t.x1.toFixed(2)}
            y2={t.y1.toFixed(2)}
            stroke={`rgb(255 255 255 / ${t.major ? 0.32 : 0.14})`}
            strokeWidth="0.5"
          />
        ))}
        <path d={arc(0, 1)} stroke="rgb(255 255 255 / 0.07)" strokeWidth="6" fill="none" strokeLinecap="round" />
        {value > 0 && (
          <path
            d={arc(0, value / 100)}
            stroke={`url(#${id}-arc)`}
            strokeWidth="6"
            fill="none"
            strokeLinecap="round"
            filter={`url(#${id}-glow)`}
          />
        )}
        {mark && <circle data-testid="alert-mark" cx={mark[0].toFixed(2)} cy={mark[1].toFixed(2)} r="1.3" fill="var(--color-down)" />}
        <text x="50" y="50" textAnchor="middle" fontSize="19" fontWeight="600" fill="var(--color-fg)" letterSpacing="-0.8">
          {Math.round(value)}%
        </text>
      </svg>
      {children && <div className="-mt-1 text-[12.5px] leading-snug">{children}</div>}
    </div>
  )
}
