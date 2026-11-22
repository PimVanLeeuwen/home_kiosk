import { Ring } from '../ui/Ring'
import { SvgLabel } from '../ui/SvgLabel'
const R = 38

/** "23:00" → 23; "07:30" → 7.5. */
const hours = (hhmm: string) => {
  const [h, m] = hhmm.split(':').map(Number)
  return (h || 0) + (m || 0) / 60
}

interface Props {
  start: string
  end: string
  enabled: boolean
  now: Date
}

/** The day as a 24-hour ring (midnight at the top) with the quiet hours lit and a mark for now. */
export function QuietRing({ start, end, enabled, now }: Props) {
  const from = hours(start)
  const span = (hours(end) - from + 24) % 24
  const at = ((now.getHours() + now.getMinutes() / 60) / 24) * 2 * Math.PI - Math.PI / 2
  return (
    <div className="relative w-28 shrink-0">
      <Ring
        role="img"
        aria-label={enabled ? `Quiet from ${start} to ${end}` : 'Quiet hours off'}
        data-on={enabled}
        className="block w-full"
        box={100}
        r={R}
        stroke={8}
        cap="butt"
        glow={3}
        color="var(--color-accent-line)"
        fraction={enabled ? span / 24 : 0}
        start={from / 24}
      >
        <circle cx={(50 + R * Math.cos(at)).toFixed(1)} cy={(50 + R * Math.sin(at)).toFixed(1)} r="3.4" fill="var(--color-fg)" />
      </Ring>
      {/* The clock's four hours just inside the ring, the span and "quiet" in the middle. */}
      {(
        [
          ['0', 50, 23],
          ['6', 76, 50],
          ['12', 50, 77],
          ['18', 24, 50],
        ] as const
      ).map(([t, x, y]) => (
        <SvgLabel key={t} x={x} y={y} w={100} h={100} className="text-label text-faint">
          {t}
        </SvgLabel>
      ))}
      <SvgLabel x={50} y={45} w={100} h={100} className="text-small font-semibold">
        {enabled ? `${start.slice(0, 2)}–${end.slice(0, 2)}` : 'off'}
      </SvgLabel>
      <SvgLabel x={50} y={58} w={100} h={100} className="text-label text-muted">
        quiet
      </SvgLabel>
    </div>
  )
}
