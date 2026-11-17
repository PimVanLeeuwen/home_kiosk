import type { ReactNode } from 'react'
import { cn } from '../../lib/cn'
import { GlowDot } from '../ui/GlowDot'

interface Props {
  on: boolean
  onClick: () => void
  children: ReactNode
  /** A glowing dot in this colour before the label, such as a news group's. */
  colour?: string
}

/** A toggle in a row of filters, as on the Alerts message log. */
export function FilterPill({ on, onClick, children, colour }: Props) {
  return (
    <button
      type="button"
      aria-pressed={on}
      onClick={onClick}
      className={cn(
        'inline-flex shrink-0 items-center gap-1.5 rounded-full border px-3 py-1 text-caption',
        on ? 'border-accent-line/40 bg-accent/20 text-fg' : 'border-glass-line bg-glass text-muted hover:text-fg',
      )}
    >
      {colour && (
        <GlowDot color={colour} size="sm" />
      )}
      {children}
    </button>
  )
}
