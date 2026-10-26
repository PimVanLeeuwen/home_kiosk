import type { CSSProperties } from 'react'
import { ahead, CORE, daysUntil, daysWord, H, SPARKS, tunnel, W } from '../../lib/countdown'
import type { Countdowns } from '../../lib/pieceTypes'
import { AnimatedNumber } from '../ui/AnimatedNumber'
import { Card } from '../ui/Card'
import { StaleNote } from '../ui/states'

const dayLine = new Intl.DateTimeFormat('en-GB', { weekday: 'short', day: 'numeric', month: 'short' })

const thenIn = (n: number) => (n === 0 ? 'today' : `in ${daysWord(n)}`)

/** The nearest countdown on Home, as on the Now panel: a tunnel of light toward the day, the days left below. */
export function CountdownCard({ data, now = new Date() }: { data: Countdowns | undefined; now?: Date }) {
  const events = ahead(data?.events, now)
  const first = events[0]
  if (!first) return null
  const [y, m, d] = first.date.split('-').map(Number)
  const days = daysUntil(first.date, now)
  const then = events[1]
  const colour = first.colour

  return (
    <Card title="Countdown" actions={<span className="text-caption text-muted">{dayLine.format(new Date(y, m - 1, d))}</span>}>
      <div className="relative -mx-5 -mt-3 overflow-hidden md:-mx-6" style={{ '--c': colour } as CSSProperties}>
        <svg viewBox={`0 0 ${W} ${H}`} className="block w-full" aria-hidden="true" data-testid="tunnel">
          <defs>
            <radialGradient id="countdown-core">
              <stop offset="0" stopColor="#fff" />
              <stop offset="0.35" stopColor={`color-mix(in srgb, ${colour} 40%, white)`} stopOpacity="0.8" />
              <stop offset="1" stopColor={colour} stopOpacity="0" />
            </radialGradient>
            <radialGradient id="countdown-wash" cx={CORE.x / W} cy={(CORE.y + 40) / H} r="0.5">
              <stop offset="0" stopColor={colour} stopOpacity="0.16" />
              <stop offset="1" stopColor={colour} stopOpacity="0" />
            </radialGradient>
            <filter id="countdown-glow" x="-20%" y="-20%" width="140%" height="140%">
              <feGaussianBlur stdDeviation="2.5" result="soft" />
              <feMerge>
                <feMergeNode in="soft" />
                <feMergeNode in="SourceGraphic" />
              </feMerge>
            </filter>
            <linearGradient id="countdown-foot" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0.55" stopColor="#000" stopOpacity="0" />
              <stop offset="1" stopColor="var(--color-card)" stopOpacity="0.92" />
            </linearGradient>
          </defs>
          <rect width={W} height={H} fill="url(#countdown-wash)" />
          <g filter="url(#countdown-glow)" fill="none">
            {tunnel(days).map((r) => (
              <ellipse
                key={r.key}
                cx={r.cx}
                cy={r.cy}
                rx={r.rx}
                ry={r.ry}
                strokeWidth={r.width}
                opacity={r.opacity}
                style={{ stroke: `color-mix(in srgb, ${colour} ${100 - r.white}%, white)` }}
              />
            ))}
          </g>
          <circle cx={CORE.x} cy={CORE.y} r="46" fill="url(#countdown-core)" />
          <circle cx={CORE.x} cy={CORE.y} r="9" fill="#fff" />
          <rect width={W} height={H} fill="url(#countdown-foot)" />
        </svg>
        {/* Sparks streaming out of the day toward you; still and hidden for reduced motion. */}
        {Array.from({ length: SPARKS }, (_, i) => (
          <span
            key={i}
            aria-hidden="true"
            style={{ '--a': `${(i * 137.5) % 360}deg`, animationDelay: `${(i * 0.26).toFixed(2)}s`, left: `${(CORE.x / W) * 100}%`, top: `${(CORE.y / H) * 100}%` } as CSSProperties}
            className="absolute -mt-[2px] -ml-[2px] block size-[4px] rounded-full bg-white opacity-0 shadow-[0_0_6px_var(--c)] motion-safe:animate-spark"
          />
        ))}
        <p className="absolute inset-x-0 bottom-1 text-center text-hero leading-none font-semibold tracking-tight md:text-giant">
          {days === 0 ? 'Today' : <AnimatedNumber value={days} />}
        </p>
      </div>
      {days > 0 && <p className="mt-2 text-center text-caption text-muted">{days === 1 ? 'day' : 'days'} to</p>}
      <p className={days > 0 ? 'text-center text-heading font-semibold' : 'mt-2 text-center text-heading font-semibold'}>{first.title}</p>
      {then && (
        <p className="mt-3 text-center text-caption text-faint">
          Then {then.title} {thenIn(daysUntil(then.date, now))}
        </p>
      )}
      {data?.stale && <StaleNote />}
    </Card>
  )
}
