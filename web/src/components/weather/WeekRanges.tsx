import { skyOf, type ForecastDay } from '../../lib/weatherTypes'

const weekday = new Intl.DateTimeFormat('en-GB', { weekday: 'short' })
const whole = (n: number) => Math.round(n)

/** A temperature's colour on the week's scale: cool blue to warm amber. */
function warmth(share: number): string {
  return `color-mix(in srgb, #f2a65a ${Math.round(share * 100)}%, #7cc4ff)`
}

/**
 * The week on the Weather page (plan.md M27, Q), as on the Now panel's week:
 * a row per day with its sky, its low and high as a range on one scale for
 * the whole week, and its highest chance of rain.
 */
export function WeekRanges({ days, today }: { days: ForecastDay[]; today: string }) {
  if (!days.length) return null
  const lo = Math.min(...days.map((d) => d.low))
  const hi = Math.max(...days.map((d) => d.high))
  const span = Math.max(1, hi - lo)
  const at = (t: number) => (t - lo) / span

  return (
    <ul className="grid gap-1">
      {days.map((d) => {
        const sky = skyOf(d.code)
        const Icon = sky.icon
        const [y, m, day] = d.date.split('-').map(Number)
        const name = d.date === today ? 'Today' : weekday.format(new Date(y, m - 1, day))
        return (
          <li
            key={d.date}
            aria-label={`${name}: ${sky.word}, ${whole(d.low)}° to ${whole(d.high)}°${d.rain_max ? `, ${d.rain_max}% chance of rain` : ''}`}
            className="grid grid-cols-[52px_28px_34px_minmax(0,1fr)_34px_44px] items-center gap-2 rounded-[10px] px-1.5 py-2 odd:bg-white/[0.015]"
          >
            <span className={d.date === today ? 'font-semibold' : 'text-muted'}>{name}</span>
            <Icon aria-hidden="true" className="size-5 text-muted" strokeWidth={1.7} />
            <span className="text-right text-small text-muted tabular-nums">{whole(d.low)}°</span>
            <span aria-hidden="true" className="relative h-1.5 rounded-full bg-white/[0.06]">
              <span
                data-range
                className="absolute inset-y-0 origin-left rounded-full motion-safe:animate-grow-x"
                style={{
                  left: `${at(d.low) * 100}%`,
                  width: `${Math.max(4, (at(d.high) - at(d.low)) * 100)}%`,
                  background: `linear-gradient(90deg, ${warmth(at(d.low))}, ${warmth(at(d.high))})`,
                }}
              />
            </span>
            <span className="text-small font-semibold tabular-nums">{whole(d.high)}°</span>
            <span className="text-right text-caption text-data-blue tabular-nums">{d.rain_max ? `${d.rain_max}%` : ''}</span>
          </li>
        )
      })}
    </ul>
  )
}
