import type { ReactNode } from 'react'
import { cn } from '../../lib/cn'
import { Card } from '../home/Card'
import { GlowArea } from '../ui/GlowArea'
import type { Tone } from '../ui/tones'

interface Props {
  title: string
  /** The figure right now, large. */
  now: ReactNode
  /** A line under it, e.g. the 24-hour peak. */
  detail?: ReactNode
  values: (number | null)[]
  label: string
  /** The chart's scale; from zero to the series' own top by default. */
  min?: number
  max?: number
  /** The figure and the line turn amber or red past a threshold. */
  tone?: Tone
  /** A colour for the line when all is well, instead of the accent. */
  color?: string
  /** A thin second line, such as upload under download, with a legend. */
  secondary?: { values: (number | null)[]; label: string; primaryLabel: string }
}

const known = (values: (number | null)[]) => values.filter((v): v is number => v != null)

/** A current value with the last 24 hours as a glowing area, running edge to edge below it. */
export function InstrumentCard({ title, now, detail, values, label, min = 0, max, tone, color, secondary }: Props) {
  const series = values.map((v) => v ?? 0)
  const alert = tone === 'warn' || tone === 'down'
  return (
    <Card title={title} className="pb-0 md:pb-0">
      <p className={cn('-mt-2 text-[23px] leading-tight font-semibold tracking-tight md:text-[30px]', tone === 'warn' && 'text-warn', tone === 'down' && 'text-down')}>
        {now}
      </p>
      {detail && <p className="mt-0.5 text-[11.5px] text-muted md:text-[12.5px]">{detail}</p>}
      {known(values).length > 1 ? (
        <>
          <div className="-mx-5 mt-2.5 md:-mx-6">
            <GlowArea
              values={series}
              label={label}
              tone={alert ? tone : 'accent'}
              color={alert ? undefined : color}
              min={min}
              max={max}
              peak
              height={64}
              secondary={secondary ? secondary.values.map((v) => v ?? 0) : undefined}
            />
          </div>
          {secondary && (
            <p className="flex gap-3 pb-2.5 text-[11.5px] text-muted" aria-hidden="true">
              <span className="flex items-center gap-1">
                <i className="inline-block h-0.5 w-2 rounded-full bg-accent-line" />
                {secondary.primaryLabel}
              </span>
              <span className="flex items-center gap-1">
                <i className="inline-block h-0.5 w-2 rounded-full bg-muted" />
                {secondary.label}
              </span>
            </p>
          )}
        </>
      ) : (
        <p className="pt-6 pb-8 text-[13px] text-faint">The 24-hour chart fills in as readings come in.</p>
      )}
    </Card>
  )
}
