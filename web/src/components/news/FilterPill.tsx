import type { ReactNode } from 'react'
import { cn } from '../../lib/cn'

interface Props {
  on: boolean
  onClick: () => void
  children: ReactNode
}

/** A toggle in a row of filters, as on the Alerts message log. */
export function FilterPill({ on, onClick, children }: Props) {
  return (
    <button
      type="button"
      aria-pressed={on}
      onClick={onClick}
      className={cn(
        'shrink-0 rounded-full border px-3 py-1 text-[12.5px]',
        on
          ? 'border-accent-line/40 bg-accent-soft text-accent-fg'
          : 'border-transparent bg-raised text-muted hover:text-fg',
      )}
    >
      {children}
    </button>
  )
}
