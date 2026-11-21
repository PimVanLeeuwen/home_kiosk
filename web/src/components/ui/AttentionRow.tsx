import { ChevronRight, CircleAlert, CircleCheck, TriangleAlert } from 'lucide-react'
import type { ReactNode } from 'react'
import { Link } from 'react-router'
import { cn } from '../../lib/cn'

const TONE = {
  warn: { icon: TriangleAlert, look: 'border-warn/30 from-warn/8', color: 'text-warn' },
  down: { icon: CircleAlert, look: 'border-down/40 from-down/8', color: 'text-down' },
} as const

interface Props {
  tone: keyof typeof TONE
  /** What needs a look, as a short sentence ("TransIP reports a problem"). */
  title: string
  /** Where and since when. */
  detail?: ReactNode
  /** Where to go about it. */
  action?: { to: string; label: string }
}

/** One thing that needs a look, at the top of an overview: its state, what and where, and the way to it. */
export function AttentionRow({ tone, title, detail, action }: Props) {
  const { icon: Icon, look, color } = TONE[tone]
  return (
    <div
      data-tone={tone}
      className={cn('flex flex-wrap items-center gap-x-3.5 gap-y-2 rounded-card border bg-linear-to-r to-transparent to-60% px-5 py-4', look)}
    >
      <Icon aria-hidden="true" className={cn('size-5 shrink-0', color)} strokeWidth={1.9} />
      <div className="min-w-0 flex-1">
        <p className="font-medium">{title}</p>
        {detail && <p className="text-small text-muted">{detail}</p>}
      </div>
      {action && (
        <Link
          to={action.to}
          className="pressable ml-8.5 inline-flex min-h-10 items-center gap-1 rounded-control border border-line bg-glass px-3.5 text-small font-medium hover:border-faint sm:ml-auto pointer-coarse:min-h-11"
        >
          {action.label}
          <ChevronRight aria-hidden="true" className="size-4" />
        </Link>
      )}
    </div>
  )
}

/** Everything that is fine, folded into one quiet line under the rows that need a look. */
export function HealthyLine({ children, link }: { children: ReactNode; link?: { to: string; label: string } }) {
  return (
    <p className="flex flex-wrap items-center gap-x-2.5 gap-y-1 text-small text-muted">
      <CircleCheck aria-hidden="true" className="size-4 shrink-0 text-up" strokeWidth={1.9} />
      <span>{children}</span>
      {link && (
        <Link to={link.to} className="hit font-medium text-accent-fg hover:underline">
          {link.label} →
        </Link>
      )}
    </p>
  )
}
