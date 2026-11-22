import type { CSSProperties, ReactNode } from 'react'
import { cn } from '../../lib/cn'

interface Props {
  /** Where its middle sits, in the drawing's own units. */
  x: number
  y: number
  /** The drawing's size in those units (its viewBox), so the label lands on the same spot at any size. */
  w: number
  h: number
  /** Which side of the label sits on x: its middle by default, its start or its end at an edge. */
  anchor?: 'start' | 'middle' | 'end'
  className?: string
  style?: CSSProperties
  children: ReactNode
}

const SHIFT = { start: 'translate-x-0', middle: '-translate-x-1/2', end: '-translate-x-full' } as const

/**
 * Text over a chart that scales (plan.md M38, 5c): HTML on top of the SVG instead of SVG text, so
 * it keeps the type scale's size (12px and up) however small the chart is drawn. Its parent is
 * `relative` and wraps the SVG; the SVG's own label says the same, so this one is hidden.
 */
export function SvgLabel({ x, y, w, h, anchor = 'middle', className, style, children }: Props) {
  return (
    <span
      aria-hidden="true"
      style={{ left: `${(x / w) * 100}%`, top: `${(y / h) * 100}%`, ...style }}
      className={cn('pointer-events-none absolute -translate-y-1/2 leading-none whitespace-nowrap', SHIFT[anchor], className)}
    >
      {children}
    </span>
  )
}
