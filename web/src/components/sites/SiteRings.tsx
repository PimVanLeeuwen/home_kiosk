import { DAY_COLOUR as COLOUR } from '../../lib/sites'
import type { Site, SiteDay } from '../../lib/types'

const point = (r: number, deg: number) => [50 + r * Math.sin((deg * Math.PI) / 180), 50 - r * Math.cos((deg * Math.PI) / 180)]

function arc(r: number, from: number, to: number) {
  const [x0, y0] = point(r, from)
  const [x1, y1] = point(r, to)
  return `M${x0.toFixed(2)} ${y0.toFixed(2)} A${r} ${r} 0 0 1 ${x1.toFixed(2)} ${y1.toFixed(2)}`
}

/**
 * One ring per site, the first outermost: 30 day segments from 30 days ago (at
 * the top) round to today. A good day quiet green, a blip amber, an outage red
 * with a glow; a site down now pulses today's segment. Sites up in the middle.
 */
export function SiteRings({ sites }: { sites: Site[] }) {
  const up = sites.filter((s) => s.up).length
  const down = sites.some((s) => s.up === false)
  const step = Math.min(5.6, 36 / Math.max(1, sites.length))
  return (
    <svg role="img" aria-label={`${up} of ${sites.length} sites up`} viewBox="0 0 100 100" className="w-full max-w-[260px]">
      <defs>
        <filter id="site-glow" x="-50%" y="-50%" width="200%" height="200%">
          <feGaussianBlur stdDeviation="1.2" result="b" />
          <feMerge>
            <feMergeNode in="b" />
            <feMergeNode in="SourceGraphic" />
          </feMerge>
        </filter>
        <radialGradient id="site-core">
          <stop offset="0" stopColor={down ? 'var(--color-down)' : 'var(--color-up)'} stopOpacity="0.3" />
          <stop offset="1" stopColor={down ? 'var(--color-down)' : 'var(--color-up)'} stopOpacity="0" />
        </radialGradient>
      </defs>
      <circle cx="50" cy="50" r="10" fill="url(#site-core)" />
      {sites.map((site, k) => {
        const r = 46 - k * step
        const faded = (0.55 - k * 0.045).toFixed(2)
        return (
          <g key={site.id} data-site={site.name}>
            {site.days.map((day, d) => {
              const now = d === site.days.length - 1 && site.up === false
              const kind: SiteDay = now ? 'down' : day
              const marked = kind === 'blip' || kind === 'down'
              return (
                <path
                  key={d}
                  data-day={kind}
                  d={arc(r, d * 12 + 1.6, d * 12 + 10.4)}
                  fill="none"
                  strokeLinecap="round"
                  stroke={kind === 'none' ? 'rgb(255 255 255 / 0.07)' : COLOUR[kind]}
                  strokeOpacity={kind === 'up' ? faded : 1}
                  strokeWidth={marked ? 3.6 : 2.7}
                  filter={marked ? 'url(#site-glow)' : undefined}
                  className={now ? 'motion-safe:animate-pulse' : undefined}
                />
              )
            })}
          </g>
        )
      })}
      <text x="50" y="52" textAnchor="middle" fontSize="7" fontWeight="600" fill={down ? 'var(--color-down)' : 'var(--color-fg)'}>
        {up}/{sites.length}
      </text>
      <text x="50" y="57" textAnchor="middle" fontSize="3" fill="var(--color-muted)" letterSpacing=".5">
        UP
      </text>
      <path d="M50 1.5 L50 5.5" stroke="rgb(255 255 255 / 0.55)" strokeWidth=".6" />
    </svg>
  )
}
