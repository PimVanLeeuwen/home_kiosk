interface Props {
  values: number[]
  label: string
  /** Scale from zero instead of the series' own minimum (sizes, not prices). */
  fromZero?: boolean
}

/** Area sparkline for a series, scaled to its own min and max by default. */
export function Sparkline({ values, label, fromZero = false }: Props) {
  if (values.length < 2) return null
  const width = 600
  const height = 120
  const min = fromZero ? 0 : Math.min(...values)
  const max = Math.max(...values)
  const span = max - min || 1
  const points = values.map((v, i) => [
    (i / (values.length - 1)) * width,
    height - 8 - ((v - min) / span) * (height - 16),
  ])
  const line = points.map(([x, y], i) => `${i ? 'L' : 'M'}${x.toFixed(1)} ${y.toFixed(1)}`).join(' ')

  return (
    <svg
      viewBox={`0 0 ${width} ${height}`}
      preserveAspectRatio="none"
      role="img"
      aria-label={label}
      className="h-[110px] w-full"
    >
      <defs>
        <linearGradient id="spark-fill" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="var(--color-accent-line)" stopOpacity="0.28" />
          <stop offset="1" stopColor="var(--color-accent-line)" stopOpacity="0" />
        </linearGradient>
      </defs>
      <path d={`${line} L${width} ${height} L0 ${height} Z`} fill="url(#spark-fill)" />
      <path d={line} fill="none" stroke="var(--color-accent-line)" strokeWidth="2" vectorEffect="non-scaling-stroke" />
    </svg>
  )
}
