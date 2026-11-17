import type { ServiceStatus } from '../lib/types'
import { STATUS_LABEL, STATUS_TONE } from '../lib/status'
import { GlowDot } from './ui/GlowDot'

/** Problems pulse slowly; starting up is a passing state and stays still. */
const NEEDS_LOOK: ServiceStatus[] = ['unhealthy', 'down', 'missing']

/** A service's status as a GlowDot, with the status as text for screen readers and on hover. */
export function StatusDot({ status, className }: { status: ServiceStatus; className?: string }) {
  return (
    <GlowDot
      tone={STATUS_TONE[status]}
      size="sm"
      halo={NEEDS_LOOK.includes(status)}
      text={STATUS_LABEL[status]}
      data-status={status}
      className={className}
    />
  )
}
