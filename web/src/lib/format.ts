// Number formatting, Dutch conventions like the kiosk (1.234, 1,2 TB).

const LOCALE = 'nl-NL'
const TB = 1e12
const GB = 1e9
const MB = 1e6

const decimals = (n: number, digits: number) =>
  new Intl.NumberFormat(LOCALE, {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  }).format(n)

export const formatCount = (n: number) => new Intl.NumberFormat(LOCALE).format(n)

/** Decimal units like the kiosk and disk vendors; small sizes step down a unit. */
export function formatBytes(bytes: number): string {
  if (bytes >= TB) return `${decimals(bytes / TB, 1)} TB`
  // One decimal below 10 GB, where whole gigabytes are too coarse (container memory).
  if (bytes >= GB) return `${decimals(bytes / GB, bytes < 10 * GB ? 1 : 0)} GB`
  return `${decimals(bytes / MB, 0)} MB`
}

/** Transfer speed: kB/s below one megabyte per second, else MB/s. */
export function formatRate(bytesPerSecond: number): string {
  if (bytesPerSecond >= MB) return `${decimals(bytesPerSecond / MB, 1)} MB/s`
  return `${decimals(bytesPerSecond / 1e3, 0)} kB/s`
}

/** A 0 to 100 percentage with one decimal: 97,2%. */
export const formatPercent = (percent: number) => `${decimals(percent, 1)}%`

export const formatMoney = (n: number, currency = 'EUR') =>
  new Intl.NumberFormat(LOCALE, { style: 'currency', currency, maximumFractionDigits: 0 }).format(n)

/** "+0,91%" / "−1,10%" with a real minus sign. */
export function formatSignedPct(n: number): string {
  const sign = n > 0 ? '+' : n < 0 ? '−' : ''
  return `${sign}${decimals(Math.abs(n), 2)}%`
}

/** Megabits per second, as the NAS reports network throughput. */
export const formatMbit = (mbps: number) => `${decimals(mbps, 1)} Mbit/s`

const time = new Intl.DateTimeFormat('en-GB', { hour: '2-digit', minute: '2-digit' })
const day = new Intl.DateTimeFormat('en-GB', { weekday: 'short', day: 'numeric', month: 'short' })

/** "today 03:31", "yesterday 03:31", "Tue 28 Sep 03:31". */
export function formatWhen(iso: string, now = new Date()): string {
  const date = new Date(iso)
  const start = (d: Date) => new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime()
  const days = Math.round((start(now) - start(date)) / 86_400_000)
  const label = days === 0 ? 'today' : days === 1 ? 'yesterday' : day.format(date)
  return `${label} ${time.format(date)}`
}

/** "just now", "5 min ago", "3 hours ago", "2 days ago", then the date. */
export function formatAgo(iso: string, now = new Date()): string {
  const seconds = Math.max(0, (now.getTime() - new Date(iso).getTime()) / 1000)
  const plural = (n: number, unit: string) => `${n} ${unit}${n === 1 ? '' : 's'} ago`
  if (seconds < 60) return 'just now'
  if (seconds < 3600) return `${Math.floor(seconds / 60)} min ago`
  if (seconds < 86_400) return plural(Math.floor(seconds / 3600), 'hour')
  if (seconds < 30 * 86_400) return plural(Math.floor(seconds / 86_400), 'day')
  return new Intl.DateTimeFormat('en-GB', { day: 'numeric', month: 'short', year: 'numeric' }).format(
    new Date(iso),
  )
}
