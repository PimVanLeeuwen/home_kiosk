import { cn } from '../../lib/cn'
import type { Severity } from '../../lib/types'

const STYLE: Record<Severity, { label: string; className: string }> = {
  error: { label: 'Error', className: 'bg-down/15 text-down' },
  warning: { label: 'Warning', className: 'bg-warn/15 text-warn' },
  ok: { label: 'OK', className: 'bg-up/15 text-up' },
  info: { label: 'Info', className: 'bg-accent-soft text-accent-fg' },
}

export function SeverityPill({ severity }: { severity: Severity }) {
  const s = STYLE[severity]
  return <span className={cn('rounded-md px-2 py-0.5 text-[11px] font-semibold', s.className)}>{s.label}</span>
}
