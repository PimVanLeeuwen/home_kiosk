/** A tiny line for a row: CPU over 24 hours. Gaps (null) break the line. */
export function MiniSpark({ values, label }: { values: (number | null)[]; label: string }) {
  const known = values.filter((v): v is number => v != null)
  if (known.length < 2) return <span className="inline-block h-5 w-20" aria-hidden="true" />
  const width = 80
  const height = 20
  const max = Math.max(...known, 0.5) // keep near-idle lines flat instead of noisy
  const step = width / Math.max(values.length - 1, 1)
  let d = ''
  values.forEach((v, i) => {
    if (v == null) return
    const x = (i * step).toFixed(1)
    const y = (height - 2 - (v / max) * (height - 4)).toFixed(1)
    d += `${d && values[i - 1] != null ? 'L' : 'M'}${x} ${y} `
  })
  return (
    <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label={label} className="h-5 w-20 shrink-0">
      <path d={d} fill="none" stroke="var(--color-accent-line)" strokeWidth="1.5" strokeLinejoin="round" />
    </svg>
  )
}
