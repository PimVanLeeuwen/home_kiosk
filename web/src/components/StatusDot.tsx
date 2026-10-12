import type { CSSProperties } from 'react'
import type { ServiceStatus } from '../lib/types'
import { cn } from '../lib/cn'
import { STATUS_LABEL } from '../lib/status'

const COLOR: Record<ServiceStatus, string> = {
  up: 'var(--color-up)',
  starting: 'var(--color-warn)',
  unhealthy: 'var(--color-warn)',
  down: 'var(--color-down)',
  missing: 'var(--color-down)',
  unknown: 'var(--color-faint)',
}

/** Problems pulse slowly; starting up is a passing state and stays still. */
const NEEDS_LOOK: ServiceStatus[] = ['unhealthy', 'down', 'missing']

/** A glowing colour dot with the status as text for screen readers and on hover. */
export function StatusDot({ status, className }: { status: ServiceStatus; className?: string }) {
  return (
    <span
      title={STATUS_LABEL[status]}
      data-status={status}
      style={{ '--glow': COLOR[status], backgroundColor: COLOR[status] } as CSSProperties}
      className={cn(
        'inline-block size-[7px] shrink-0 rounded-full',
        status !== 'unknown' &&
          'shadow-[0_0_0_3px_color-mix(in_srgb,var(--glow)_16%,transparent),0_0_8px_var(--glow)]',
        NEEDS_LOOK.includes(status) && 'motion-safe:animate-halo',
        className,
      )}
    >
      <span className="sr-only">{STATUS_LABEL[status]}</span>
    </span>
  )
}
