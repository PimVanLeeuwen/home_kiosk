import { cn } from '../../lib/cn'

interface Props {
  label: string
  value: string
  pct: number
  /** Colour the bar as a warning or problem. */
  tone?: 'ok' | 'warn' | 'down'
}

export function Meter({ label, value, pct, tone = 'ok' }: Props) {
  const bar = tone === 'down' ? 'bg-down' : tone === 'warn' ? 'bg-warn' : 'bg-accent-line'
  return (
    <div>
      <div className="flex justify-between gap-3 text-[13px]">
        <span className="text-muted">{label}</span>
        <span className="truncate">{value}</span>
      </div>
      <div
        role="meter"
        aria-label={label}
        aria-valuenow={Math.round(pct)}
        aria-valuemin={0}
        aria-valuemax={100}
        className="mt-1.5 h-1.5 overflow-hidden rounded-full bg-raised"
      >
        <div className={cn('h-full rounded-full', bar)} style={{ width: `${Math.min(100, Math.max(0, pct))}%` }} />
      </div>
    </div>
  )
}
