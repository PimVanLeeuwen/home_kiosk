import type { ReactNode } from 'react'
import { Sparkline } from '../home/Sparkline'

interface Props {
  title: string
  /** The figure right now, large. */
  now: string
  /** A line under it, e.g. the 24-hour peak. */
  detail?: ReactNode
  values: (number | null)[]
  label: string
  /** A fixed top of the chart scale, e.g. 100 for percentages. */
  max?: number
}

/** A current value with its last 24 hours drawn underneath. */
export function ChartCard({ title, now, detail, values, label, max }: Props) {
  const known = values.filter((v): v is number => v != null)
  return (
    <section aria-label={title} className="min-w-0 rounded-[14px] border border-line-soft bg-card px-5 pt-4 pb-3">
      <h2 className="text-[13px] font-semibold text-muted">{title}</h2>
      <p className="mt-1 text-[24px] font-semibold tracking-tight">{now}</p>
      {detail && <p className="text-[12.5px] text-faint">{detail}</p>}
      {known.length > 1 ? (
        <Sparkline values={values.map((v) => v ?? 0)} label={label} fromZero max={max} />
      ) : (
        <p className="py-8 text-[13px] text-faint">The 24-hour chart fills in as readings come in.</p>
      )}
    </section>
  )
}
