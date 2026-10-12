import { cn } from '../../lib/cn'
import type { Severity } from '../../lib/types'

const STYLE: Record<Severity, { label: string; className: string }> = {
  error: { label: 'Error', className: 'bg-down/15 text-down' },
  warning: { label: 'Warning', className: 'bg-warn/15 text-warn' },
  ok: { label: 'OK', className: 'bg-up/15 text-up' },
  info: { label: 'Info', className: 'bg-accent/20 text-accent-fg' },
}

export function SeverityPill({ severity }: { severity: Severity }) {
  const s = STYLE[severity]
  return <span className={cn('rounded-[6px] px-1.5 py-px text-[10.5px] font-bold tracking-[0.06em] uppercase', s.className)}>{s.label}</span>
}
