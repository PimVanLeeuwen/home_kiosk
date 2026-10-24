import type { ReactNode } from 'react'
import { cn } from '../../lib/cn'
import { Card } from './Card'
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

/** One of a page's headline numbers: a small card with a label, a large figure and what goes with it. */
export function StatTile({ title, figure, sub, tone, children }: Props) {
  return (
    <Card title={title} className="px-3.5 py-3.5 md:px-4.5 md:py-4">
      <div
        style={tone ? { color: TONE_COLOR[tone] } : undefined}
        className="-mt-2 text-stat leading-tight font-semibold tracking-tight md:text-page"
      >
        {typeof figure === 'number' ? <AnimatedNumber value={figure} /> : figure}
      </div>
      {sub && <p className="mt-0.5 text-caption text-muted">{sub}</p>}
      {children}
    </Card>
  )
}

const COLUMNS = { 2: 'xl:grid-cols-2', 3: 'xl:grid-cols-3', 4: 'xl:grid-cols-4' } as const

/** A page's headline numbers in one row: two per line on the phone, all in a row on a wide screen. */
export function StatTiles({ label, count, children }: { label: string; count: keyof typeof COLUMNS; children: ReactNode }) {
  return (
    <section aria-label={label} className={cn('mb-5 grid grid-cols-2 gap-2.5 md:gap-4', COLUMNS[count])}>
      {children}
    </section>
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
