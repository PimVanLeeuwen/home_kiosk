import type { ReactNode } from 'react'
import { cn } from '../../lib/cn'
import { CardHeader } from './Card'
import { CELL_SPAN, InCellGrid } from './cellContext'
import { headerId } from './titleStyles'

const COLUMNS = {
  2: 'sm:grid-cols-2',
  3: 'sm:grid-cols-2 xl:grid-cols-3',
  4: 'grid-cols-2 xl:grid-cols-4',
} as const

interface GridProps {
  /** What the cells are together, for a screen reader ("The NAS at a glance"). */
  label: string
  /** Cells in a row on a wide screen; fewer on smaller ones. */
  columns: keyof typeof COLUMNS
  className?: string
  children: ReactNode
}

/**
 * Neo-minimal cells that share their hairlines: one rounded box, cut into cells by 1px
 * lines. Each cell draws its own line (a 1px spread shadow into the gap), so a row that is
 * not full shows an empty cell, never a block of line colour. A Card or Surface placed in it
 * (also through a wrapper, such as Home's CardSlot) becomes a cell.
 */
export function CellGrid({ label, columns, className, children }: GridProps) {
  return (
    <section
      aria-label={label}
      className={cn('grid gap-px overflow-hidden rounded-card border border-line-soft bg-card', COLUMNS[columns], className)}
    >
      <InCellGrid.Provider value={true}>{children}</InCellGrid.Provider>
    </section>
  )
}


interface CellProps {
  /** Its header, as on a card; without one the cell is bare. */
  title?: string
  link?: { to: string; label: string }
  note?: ReactNode
  actions?: ReactNode
  /** How many columns the cell takes. */
  span?: keyof typeof CELL_SPAN
  /** For layout only (padding at the bottom for a sparkline, for example). */
  className?: string
  children: ReactNode
}

/** One cell of a CellGrid: flat, with an optional card header. */
export function Cell({ title, link, note, actions, span = 1, className, children }: CellProps) {
  const id = title ? headerId(title) : undefined
  return (
    <InCellGrid.Provider value={false}>
      <div
        role={title ? 'group' : undefined}
        aria-labelledby={id}
        className={cn('relative min-w-0 bg-card px-5 py-5 shadow-[0_0_0_1px_var(--color-line-soft)] md:px-5.5', CELL_SPAN[span], className)}
      >
        {title && id && <CardHeader id={id} title={title} link={link} note={note} actions={actions} />}
        {children}
      </div>
    </InCellGrid.Provider>
  )
}
