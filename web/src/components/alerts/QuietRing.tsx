const R = 38
const C = 2 * Math.PI * R

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
    <svg
      role="img"
      aria-label={enabled ? `Quiet from ${start} to ${end}` : 'Quiet hours off'}
      data-on={enabled}
      viewBox="0 0 100 100"
      className="w-24 shrink-0"
    >
      <circle cx="50" cy="50" r={R} fill="none" stroke="rgb(255 255 255 / 0.08)" strokeWidth="8" />
      {enabled && span > 0 && (
        <circle
          data-testid="quiet-span"
          cx="50"
          cy="50"
          r={R}
          fill="none"
          stroke="var(--color-accent-line)"
          strokeWidth="8"
          className="motion-safe:animate-sweep"
          strokeDasharray={`${((span / 24) * C).toFixed(2)} ${C.toFixed(2)}`}
          strokeDashoffset={(-(from / 24) * C).toFixed(2)}
          transform="rotate(-90 50 50)"
          style={{ filter: 'drop-shadow(0 0 3px var(--color-accent-line))' }}
        />
      )}
      <circle cx={(50 + R * Math.cos(at)).toFixed(1)} cy={(50 + R * Math.sin(at)).toFixed(1)} r="3.4" fill="var(--color-fg)" />
      {[
        ['0', 50, 7],
        ['6', 95, 52],
        ['12', 50, 99],
        ['18', 5, 52],
      ].map(([t, x, y]) => (
        <text key={t} x={x} y={y} fontSize="7" fill="var(--color-faint)" textAnchor="middle">
          {t}
        </text>
      ))}
      <text x="50" y="49" textAnchor="middle" fontSize="9" fontWeight="600" fill="var(--color-fg)">
        {enabled ? `${start.slice(0, 2)}–${end.slice(0, 2)}` : 'off'}
      </text>
      <text x="50" y="60" textAnchor="middle" fontSize="6.5" fill="var(--color-muted)">
        quiet
      </text>
    </svg>
  )
}
