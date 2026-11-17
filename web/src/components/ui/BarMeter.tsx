import { cn } from '../../lib/cn'
import type { Tone } from './tones'

const BAR: Record<Tone, string> = {
  accent: 'bg-accent-line',
  up: 'bg-up',
  warn: 'bg-warn',
  down: 'bg-down',
  muted: 'bg-faint',
}

interface Props {
  label: string
  value: string
  pct: number
  /** The bar's colour: violet while all is well, amber or red as it fills up. */
  tone?: Tone
}

/** A labelled bar from 0 to 100, its value on the right: a pool's fill, a budget spent. */
export function BarMeter({ label, value, pct, tone = 'accent' }: Props) {
  return (
    <div>
      <div className="flex justify-between gap-3 text-small">
        <span className="text-muted">{label}</span>
        <span className="truncate">{value}</span>
      </div>
      <div
        role="meter"
        aria-label={label}
        aria-valuenow={Math.round(pct)}
        aria-valuemin={0}
        aria-valuemax={100}
        data-tone={tone}
        className="mt-1.5 h-1.5 overflow-hidden rounded-full bg-raised"
      >
        <div className={cn('h-full origin-left rounded-full motion-safe:animate-grow-x', BAR[tone])} style={{ width: `${Math.min(100, Math.max(0, pct))}%` }} />
      </div>
    </div>
  )
}
