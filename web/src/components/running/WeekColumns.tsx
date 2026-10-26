import { cn } from '../../lib/cn'
import { km, type WeekDay } from '../../lib/running'
import { RouteArt } from './RouteArt'

const letter = new Intl.DateTimeFormat('en-GB', { weekday: 'narrow' })
const longDay = new Intl.DateTimeFormat('en-GB', { weekday: 'long' })

/**
 * This week against the plan (plan.md M28, B): a column per day, Runna's plan
 * as a glass outline, what you ran poured in as warm light, and each run's
 * route in miniature above it. Today is lit.
 */
export function WeekColumns({ week, today }: { week: WeekDay[]; today: string }) {
  const top = Math.max(1000, ...week.map((d) => Math.max(d.planned_m, d.done_m)))
  return (
    <ul className="grid grid-cols-7 items-end gap-2">
      {week.map((d) => {
        const [y, m, day] = d.date.split('-').map(Number)
        const date = new Date(y, m - 1, day)
        const isToday = d.date === today
        const words = [
          d.planned_m ? `${km(d.planned_m)} km planned${d.sessions.length ? ` (${d.sessions.join(', ')})` : ''}` : 'nothing planned',
          d.done_m ? `${km(d.done_m)} km run` : null,
        ]
          .filter(Boolean)
          .join(', ')
        return (
          <li key={d.date} aria-label={`${longDay.format(date)}: ${words}`} className="grid justify-items-center gap-1.5">
            <span aria-hidden="true" className="grid h-7 w-full place-items-end">
              {d.routes[0] && <RouteArt points={d.routes[0]} width={60} height={40} pad={4} mini className="h-7 w-full" />}
            </span>
            <span aria-hidden="true" className="relative h-28 w-full max-w-9">
              {d.planned_m > 0 && (
                <span
                  data-planned
                  className="absolute inset-x-0 bottom-0 rounded-[8px] border border-white/18 bg-white/[0.03]"
                  style={{ height: `${(d.planned_m / top) * 100}%` }}
                />
              )}
              {d.done_m > 0 && (
                <span
                  data-done
                  className="absolute inset-x-0.5 bottom-0 origin-bottom rounded-[7px] bg-linear-to-t from-[#c8692e] to-[#ffc98f] shadow-[0_0_18px_-4px_#f2a65a] motion-safe:animate-grow"
                  style={{ height: `${(d.done_m / top) * 100}%` }}
                />
              )}
              {!d.planned_m && !d.done_m && <span className="absolute inset-x-3 bottom-0 h-1 rounded-full bg-white/10" />}
            </span>
            <span className={cn('text-label font-semibold', isToday ? 'text-fg' : 'text-faint')}>{letter.format(date)}</span>
            {isToday && <span aria-hidden="true" className="-mt-1 size-1 rounded-full bg-accent-line shadow-[0_0_6px_var(--color-accent-line)]" />}
          </li>
        )
      })}
    </ul>
  )
}
