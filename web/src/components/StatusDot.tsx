import type { ServiceStatus } from '../lib/types'
import { cn } from '../lib/cn'
import { STATUS_LABEL } from '../lib/status'

const DOT: Record<ServiceStatus, string> = {
  up: 'bg-up shadow-[0_0_0_3px_rgb(63_185_127/0.15)]',
  starting: 'bg-warn shadow-[0_0_0_3px_rgb(224_162_59/0.15)]',
  unhealthy: 'bg-warn shadow-[0_0_0_3px_rgb(224_162_59/0.15)]',
  down: 'bg-down shadow-[0_0_0_3px_rgb(229_100_106/0.15)]',
  missing: 'bg-down shadow-[0_0_0_3px_rgb(229_100_106/0.15)]',
  unknown: 'bg-faint',
}

/** Colour dot with the status as text for screen readers and on hover. */
export function StatusDot({ status, className }: { status: ServiceStatus; className?: string }) {
  return (
    <span
      title={STATUS_LABEL[status]}
      className={cn('inline-block size-[7px] shrink-0 rounded-full', DOT[status], className)}
    >
      <span className="sr-only">{STATUS_LABEL[status]}</span>
    </span>
  )
}
