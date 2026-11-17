import { CONNECTION_LABEL, connectionFor } from '../lib/connection'
import { cn } from '../lib/cn'
import { GlowDot } from './ui/GlowDot'

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
      <GlowDot tone="up" size="sm" />
      <span>{CONNECTION_LABEL[connection]}</span>
      {showHost && <span className="ml-auto truncate font-mono text-faint">{host}</span>}
    </div>
  )
}
