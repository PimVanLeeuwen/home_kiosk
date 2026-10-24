import type { ReactNode } from 'react'
import { cn } from '../../lib/cn'

interface Props {
  label: string
  value: ReactNode
  /** Below the value: a sparkline, dots, a short note. */
  children?: ReactNode
  className?: string
}

/** A small glass tile inside a card: a label, a figure, and what goes with it. */
export function GlassTile({ label, value, children, className }: Props) {
  return (
    <div className={cn('min-w-0 rounded-[11px] border border-glass-line bg-glass px-[11px] py-[9px]', className)}>
      <p className="text-micro font-semibold tracking-[0.08em] text-faint uppercase">{label}</p>
      <p className="mt-px mb-[3px] truncate text-title font-semibold">{value}</p>
      {children}
    </div>
  )
}
