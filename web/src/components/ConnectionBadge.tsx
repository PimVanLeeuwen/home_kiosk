import { CONNECTION_LABEL, connectionFor } from '../lib/connection'
import { cn } from '../lib/cn'

interface Props {
  /** Also show the host name, in mono (sidebar footer). */
  showHost?: boolean
  className?: string
}

export function ConnectionBadge({ showHost = false, className }: Props) {
  const host = window.location.hostname
  const connection = connectionFor(host)

  return (
    <div className={cn('flex items-center gap-2 text-xs text-muted', className)}>
      <span
        aria-hidden="true"
        className="size-[7px] shrink-0 rounded-full bg-up shadow-[0_0_0_3px_--alpha(var(--color-up)/15%)]"
      />
      <span>{CONNECTION_LABEL[connection]}</span>
      {showHost && <span className="ml-auto truncate font-mono text-faint">{host}</span>}
    </div>
  )
}
