import type { ReactNode } from 'react'
import { cn } from '../../lib/cn'
import type { Tone } from './tones'

const STYLE: Record<Tone, string> = {
  up: 'text-up bg-up/13',
  down: 'text-down bg-down/14',
  warn: 'text-warn bg-warn/15',
  accent: 'text-accent-fg bg-accent/20',
  muted: 'text-muted bg-raised',
}

/** A small uppercase state label: "Healthy", "All safe", "+0,91% today". */
export function Pill({ tone, children, className }: { tone: Tone; children: ReactNode; className?: string }) {
  return (
    <span
      className={cn(
        'inline-block rounded-full px-[9px] py-0.5 text-label font-semibold tracking-[0.06em] whitespace-nowrap uppercase',
        STYLE[tone],
        className,
      )}
    >
      {children}
    </span>
  )
}
