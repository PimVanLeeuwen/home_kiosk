import type { CSSProperties } from 'react'
import { cn } from '../../lib/cn'
import { formatTime } from '../../lib/format'
import { focusOf, hoursOf, isPast, ribbonX, todayShows } from '../../lib/today'
import type { Today } from '../../lib/types'
import { GlowDot } from '../ui/GlowDot'
import { Card } from '../ui/Card'
import { StaleNote } from '../ui/states'
import { MinutesRing } from './MinutesRing'

const dayLine = new Intl.DateTimeFormat('en-GB', { weekday: 'short', day: 'numeric', month: 'short' })

/**
 * Today on Home, the Now panel's calendar card: the event under way or next
 * with a countdown in its calendar's colour, all-day events, the day from
 * 07:00 to 23:00 as a ribbon with a glowing now line, then the rest of the
 * day. Left out on a day without events.
 */
export function TodayCard({ data }: { data: Today | undefined }) {
  const now = new Date()
  if (!todayShows(data, now)) return null

  const today = data
  const focus = focusOf(today.events, now)
  const nowX = ribbonX(now.getHours() + now.getMinutes() / 60)
  const rest = today.events.filter((e) => e !== focus?.event)
  const total = today.events.length + today.all_day.length

  return (
    <Card title={`Today · ${dayLine.format(now)}`} note={`${total} ${total === 1 ? 'event' : 'events'}`}>
      {focus ? (
        <div className="relative grid grid-cols-[80px_minmax(0,1fr)] items-center gap-3.5 md:grid-cols-[96px_minmax(0,1fr)] md:gap-4.5">
          <MinutesRing minutes={focus.minutes} color={focus.event.color} label={focus.now ? 'min left' : 'min'} className="w-20 shrink-0 md:w-24" />
          <div className="min-w-0">
            <p className="text-label eyebrow" style={{ color: focus.event.color }}>
              {focus.now ? 'Now' : 'Next'} · {focus.event.calendar}
            </p>
            <p className="my-0.5 text-heading leading-tight font-semibold tracking-tight md:text-stat">{focus.event.title}</p>
            <p className="text-muted">
              {focus.now
                ? `until ${formatTime(focus.event.end!)}`
                : `${formatTime(focus.event.start!)}${focus.event.end ? ` to ${formatTime(focus.event.end)}` : ''}`}
            </p>
          </div>
        </div>
      ) : (
        today.events.length > 0 && (
          <p className="relative mb-1 flex items-center gap-2.5 text-muted">
            <GlowDot tone="up" />
            Nothing more today
          </p>
        )
      )}

      {today.all_day.length > 0 && (
        <ul aria-label="All day" className="relative mt-3.5 flex flex-wrap gap-1.5">
          {today.all_day.map((e, i) => (
            <li
              key={`${e.calendar_id}-${i}`}
              style={{ '--c': e.color } as CSSProperties}
              className="rounded-full border border-(--c)/35 bg-(--c)/8 px-2.5 py-0.5 text-small text-(--c)"
            >
              {e.title}
            </li>
          ))}
        </ul>
      )}

      {today.events.length > 0 && (
        <>
          <div role="img" aria-label="The day from 07:00 to 23:00" className="relative mt-5 h-3.5 rounded-full bg-white/5">
            {today.events.map((e, i) => {
              const from = ribbonX(hoursOf(e.start!))
              const to = ribbonX(e.end ? hoursOf(e.end) : hoursOf(e.start!) + 0.25)
              const past = isPast(e, now)
              return (
                <i
                  key={`${e.calendar_id}-${i}`}
                  data-past={past || undefined}
                  style={{ left: `${from}%`, width: `${Math.max(1, to - from)}%`, backgroundColor: e.color, boxShadow: past ? 'none' : `0 0 8px ${e.color}88` }}
                  className={cn('absolute inset-y-0.5 block rounded-full', past ? 'opacity-30' : 'opacity-85')}
                />
              )
            })}
            <b
              style={{ left: `${nowX}%` }}
              className="absolute -inset-y-1 -ml-px block w-0.5 rounded-tag bg-white shadow-[0_0_8px_#fff,0_0_14px_--alpha(var(--color-accent-fg)/90%)]"
            />
          </div>
          <p aria-hidden="true" className="relative mt-1 flex justify-between text-label text-faint">
            <span>07:00</span>
            <span>12:00</span>
            <span>17:00</span>
            <span>23:00</span>
          </p>
        </>
      )}

      {rest.length > 0 && (
        <ul aria-label="The rest of the day" className="relative mt-3.5">
          {rest.map((e, i) => {
            const past = isPast(e, now)
            return (
              <li
                key={`${e.calendar_id}-${i}`}
                data-past={past || undefined}
                className={cn('grid grid-cols-[46px_10px_minmax(0,1fr)_auto] items-center gap-2.5 border-glass-line py-1.5 text-small not-first:border-t', past && 'opacity-45')}
              >
                <span className="text-small text-muted">{formatTime(e.start!)}</span>
                <GlowDot color={e.color} />
                <span className={cn('truncate', past && 'line-through decoration-white/30')}>{e.title}</span>
                <span className="text-small text-faint">{e.calendar}</span>
              </li>
            )
          })}
        </ul>
      )}

      {Object.keys(today.errors).length > 0 && (
        <p className="relative mt-3 text-small text-warn">Not read just now: {Object.keys(today.errors).join(', ')}.</p>
      )}
      {today.stale && <StaleNote />}
    </Card>
  )
}
