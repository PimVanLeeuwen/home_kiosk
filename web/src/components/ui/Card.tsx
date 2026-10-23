import type { HTMLAttributes, ReactNode } from 'react'
import { Link } from 'react-router'
import { cn } from '../../lib/cn'

/** The paddings a surface comes in: a card, a list of rows, a compact group, or none (the content sets its own). */
const PADDING = {
  card: 'px-5 py-5 md:px-6',
  list: 'px-5 py-2 md:px-6',
  compact: 'p-3 md:p-4',
  none: '',
} as const

interface SurfaceProps extends HTMLAttributes<HTMLElement> {
  as?: 'section' | 'div' | 'ul' | 'article'
  padding?: keyof typeof PADDING
}

/**
 * The hub's card surface: rounded, a soft line, and a faint sheen at the top
 * as on the desk panels' glass. Every card-like box is one of these.
 */
export function Surface({ as: Tag = 'div', padding = 'card', className, ...rest }: SurfaceProps) {
  return (
    <Tag
      {...rest}
      className={cn(
        'relative min-w-0 overflow-hidden rounded-[14px] border border-line-soft bg-card bg-linear-to-b from-white/[0.022] to-transparent to-40%',
        PADDING[padding],
        className,
      )}
    />
  )
}

interface Props {
  title: string
  /** "Open →" style link to the full section. */
  link?: { to: string; label: string }
  /** Controls at the right of the title, e.g. a period switch. */
  actions?: ReactNode
  className?: string
  children: ReactNode
}

/** A surface with the hub's card header: a small title, and actions or a link on the right. */
export function Card({ title, link, actions, className, children }: Props) {
  const id = `card-${title.toLowerCase().replace(/\W+/g, '-')}`
  return (
    <Surface as="section" aria-labelledby={id} className={className}>
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <h2 id={id} className="text-[13px] font-semibold text-muted">
          {title}
        </h2>
        {(actions || link) && (
          <div className="flex flex-wrap items-center gap-3">
            {actions}
            {link && (
              <Link to={link.to} className="text-[13px] font-medium text-accent-fg hover:underline">
                {link.label} →
              </Link>
            )}
          </div>
        )}
      </div>
      {children}
    </Surface>
  )
}
