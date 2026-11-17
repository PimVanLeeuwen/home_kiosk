import type { ReactNode } from 'react'
import { cn } from '../../lib/cn'
import { TONE_TINT, type Tone } from './tones'

/** A small uppercase state label: "Healthy", "All safe", "+0,91% today". */
export function Pill({ tone, children, className }: { tone: Tone; children: ReactNode; className?: string }) {
  return (
    <span
      className={cn(
        'inline-block rounded-full px-[9px] py-0.5 text-label eyebrow whitespace-nowrap',
        TONE_TINT[tone],
        className,
      )}
    >
      {children}
    </span>
  )
}
