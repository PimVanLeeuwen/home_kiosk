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
  if (bytes >= GB) return `${decimals(bytes / GB, 0)} GB`
  return `${decimals(bytes / MB, 0)} MB`
}

/** Transfer speed: kB/s below one megabyte per second, else MB/s. */
export function formatRate(bytesPerSecond: number): string {
  if (bytesPerSecond >= MB) return `${decimals(bytesPerSecond / MB, 1)} MB/s`
  return `${decimals(bytesPerSecond / 1e3, 0)} kB/s`
}

/** A 0 to 100 percentage with one decimal: 97,2%. */
export const formatPercent = (percent: number) => `${decimals(percent, 1)}%`
