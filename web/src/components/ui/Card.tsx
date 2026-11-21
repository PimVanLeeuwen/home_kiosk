import type { HTMLAttributes, ReactNode } from 'react'
import { Link } from 'react-router'
import { cn } from '../../lib/cn'
import { headerId, titleClass } from './titleStyles'

/**
 * The paddings a surface comes in: a card, a list of rows, a compact group, a page's
 * headline tile, a card whose chart runs to the bottom edge, or none (the content sets its own).
 */
const PADDING = {
  card: 'px-5 py-5 md:px-6',
  list: 'px-5 py-2 md:px-6',
  compact: 'p-3 md:p-4',
  tile: 'px-3.5 py-3.5 md:px-4.5 md:py-4',
  chart: 'px-5 pt-5 md:px-6',
  none: '',
} as const

/**
 * What a surface looks like: the card (a flat neo-minimal cell, a hairline edge), a box that
 * holds a problem or a warning, or bare (rounded and edged, its background left to the
 * caller: a photo, a picture of its own).
 */
const LOOK = {
  card: 'border-line-soft bg-card',
  down: 'border-down/40 bg-card',
  warn: 'border-warn/30 bg-warn/5',
  bare: 'border-line-soft',
} as const

export type SurfacePadding = keyof typeof PADDING

interface SurfaceProps extends HTMLAttributes<HTMLElement> {
  as?: 'section' | 'div' | 'ul' | 'article'
  padding?: SurfacePadding
  look?: keyof typeof LOOK
}

/** The hub's card surface: rounded, flat, a hairline edge. Every card-like box is one of these. */
export function Surface({ as: Tag = 'div', padding = 'card', look = 'card', className, ...rest }: SurfaceProps) {
  // `className` is for layout (grid, margins, height); padding and colours come from the props.
  return (
    <Tag
      {...rest}
      data-look={look === 'card' ? undefined : look}
      className={cn('relative min-w-0 overflow-hidden rounded-card border', LOOK[look], PADDING[padding], className)}
    />
  )
}

interface HeaderProps {
  /** The id the surface's aria-labelledby points at. */
  id: string
  title: string
  /** "Open →" style link to the full section. */
  link?: { to: string; label: string }
  /** A quiet word at the right of the title: where the data is from, its period, a count. */
  note?: ReactNode
  /** Controls or a status pill at the right of the title, e.g. a period switch. */
  actions?: ReactNode
}

/** A card's or cell's header: a small sentence-case title, and on the right a note, actions and a link, in that order. */
export function CardHeader({ id, title, link, note, actions }: HeaderProps) {
  return (
    <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
      <h2 id={id} className={titleClass}>
        {title}
      </h2>
      {(note || actions || link) && (
        <div className="flex flex-wrap items-center gap-3">
          {note && <span className="text-small text-faint">{note}</span>}
          {actions}
          {link && (
            <Link to={link.to} className="hit text-small font-medium text-accent-fg hover:underline">
              {link.label} →
            </Link>
          )}
        </div>
      )}
    </div>
  )
}

interface Props extends Omit<HeaderProps, 'id'> {
  /** The surface's padding: a card's own, a headline tile's, or a chart's (no bottom padding). */
  padding?: SurfacePadding
  /** For layout only (grid placement, margins); padding and colours come from the props. */
  className?: string
  children: ReactNode
}

/**
 * A surface with the hub's card header: a small sentence-case title, and on the right
 * always in this order a note, actions (a pill or controls), and a link.
 */
export function Card({ title, link, note, actions, padding, className, children }: Props) {
  const id = headerId(title)
  return (
    <Surface as="section" aria-labelledby={id} padding={padding} className={className}>
      <CardHeader id={id} title={title} link={link} note={note} actions={actions} />
      {children}
    </Surface>
  )
}
