import type { ReactNode } from 'react'
import { Link } from 'react-router'
import { cn } from '../../lib/cn'

interface Props {
  title: string
  /** "Open →" style link to the full section. */
  link?: { to: string; label: string }
  className?: string
  children: ReactNode
}

export function Card({ title, link, className, children }: Props) {
  const id = `card-${title.toLowerCase().replace(/\W+/g, '-')}`
  return (
    <section
      aria-labelledby={id}
      className={cn('min-w-0 rounded-[14px] border border-line-soft bg-card px-5 py-5 md:px-6', className)}
    >
      <div className="mb-4 flex items-center justify-between gap-3">
        <h2 id={id} className="text-[13px] font-semibold text-muted">
          {title}
        </h2>
        {link && (
          <Link to={link.to} className="text-[13px] font-medium text-accent-fg hover:underline">
            {link.label} →
          </Link>
        )}
      </div>
      {children}
    </section>
  )
}

/** Shown in a card whose source is not answering. */
export function Unavailable({ what }: { what: string }) {
  return <p className="text-muted">{what} is not available right now.</p>
}

export function Loading() {
  return (
    <p role="status" className="text-muted">
      Loading…
    </p>
  )
}

export function StaleNote() {
  return <p className="mt-3 text-[12px] text-warn">Showing the last known figures.</p>
}
