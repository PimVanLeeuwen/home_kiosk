import type { ReactNode } from 'react'
import { Card } from './Card'
import { CellGrid } from './CellGrid'
import { TONE_COLOR, type Tone } from './tones'
import { AnimatedNumber } from './AnimatedNumber'

interface Props {
  title: string
  /** The figure, large; a plain number moves to its new value when it changes. */
  figure: ReactNode
  /** A line under the figure. */
  sub?: ReactNode
  /** The figure in a state's colour (a loss, a problem). */
  tone?: Tone
  /** Below: a small chart, dots, a short list. */
  children?: ReactNode
}

/** One of a page's headline numbers: a cell with a label, a large light figure and what goes with it. */
export function StatTile({ title, figure, sub, tone, children }: Props) {
  return (
    <Card title={title} padding="tile">
      <div
        style={tone ? { color: TONE_COLOR[tone] } : undefined}
        className="-mt-2 text-stat leading-tight font-medium tracking-[-0.035em] md:text-page"
      >
        {typeof figure === 'number' ? <AnimatedNumber value={figure} /> : figure}
      </div>
      {sub && <p className="mt-0.5 text-small text-muted">{sub}</p>}
      {children}
    </Card>
  )
}

/**
 * A page's headline numbers as one row of hairline cells (plan.md M38, 5d): two per line on a
 * phone, all in a row on a wide screen; an odd one out on the last line takes the full width.
 */
export function StatTiles({ label, count, children }: { label: string; count: 2 | 3 | 4; children: ReactNode }) {
  return (
    <CellGrid
      label={label}
      columns={count}
      className="mb-5 grid-cols-2 max-xl:[&>*:last-child:nth-child(odd)]:col-span-2"
    >
      {children}
    </CellGrid>
  )
}

/** "18 / 21": a count with its total smaller beside it. */
export function OutOf({ n, of, unit }: { n: number; of: number; unit?: string }) {
  return (
    <>
      <AnimatedNumber value={n} /> <span className="text-[0.55em] font-medium text-muted">/ {of}{unit ? ` ${unit}` : ''}</span>
    </>
  )
}
