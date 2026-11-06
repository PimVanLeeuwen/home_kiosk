// One holding's last five trading days for the Portfolio page's week card, as the House
// panel's Stock screen shows them (collector app/desk_stock.py): a random holding each
// visit, a shuffle for another.

/** /api/portfolio/weeks: every holding's week, half-hourly, from Yahoo. */
export interface StockWeek {
  symbol: string
  currency: string | null
  price: number
  /** The close before the five days, which the week's change is measured from. */
  previous_close: number | null
  /** The exchange's time zone, for its trading days. */
  zone: string
  points: { t: string; price: number }[]
}

export interface StockWeeks {
  as_of: string
  stale: boolean
  stocks: StockWeek[]
}

export interface WeekView {
  /** The week's change in percent, from the previous close to the latest price. */
  change: number
  base: number
  /** Each trading day: its first point and its short name ("Mon"). */
  days: { at: number; label: string }[]
  high: number
  low: number
}

function dayFormat(zone: string, options: Intl.DateTimeFormatOptions): Intl.DateTimeFormat {
  try {
    return new Intl.DateTimeFormat('en-GB', { ...options, timeZone: zone })
  } catch {
    return new Intl.DateTimeFormat('en-GB', { ...options, timeZone: 'UTC' })
  }
}

/** The figures around one week's line; null without a line to draw. */
export function weekView(stock: StockWeek): WeekView | null {
  const prices = stock.points.map((p) => p.price)
  if (prices.length < 2) return null
  const base = stock.previous_close || prices[0]
  const key = dayFormat(stock.zone, { year: 'numeric', month: '2-digit', day: '2-digit' })
  const name = dayFormat(stock.zone, { weekday: 'short' })
  const days: WeekView['days'] = []
  let seen = ''
  stock.points.forEach((p, i) => {
    const date = new Date(p.t)
    const day = key.format(date)
    if (day !== seen) {
      seen = day
      days.push({ at: i, label: name.format(date) })
    }
  })
  const high = prices.indexOf(Math.max(...prices))
  const low = prices.indexOf(Math.min(...prices))
  return { change: ((stock.price - base) / base) * 100, base, days, high, low }
}

/** "Wed 14:30" in the exchange's own time. */
export function pointTime(stock: StockWeek, i: number): string {
  return dayFormat(stock.zone, { weekday: 'short', hour: '2-digit', minute: '2-digit' }).format(new Date(stock.points[i].t))
}

const decimals = (n: number, digits: number) =>
  new Intl.NumberFormat('nl-NL', { minimumFractionDigits: digits, maximumFractionDigits: digits }).format(n)

/** A share price in its own currency: "$ 181,60", "€ 1.295,00"; London's pence as "1.234,5p". */
export function formatPrice(n: number, currency: string | null): string {
  if (currency === 'GBp' || currency === 'GBX') return `${decimals(n, 1)}p`
  if (!currency) return decimals(n, 2)
  try {
    return new Intl.NumberFormat('nl-NL', { style: 'currency', currency, minimumFractionDigits: 2 }).format(n)
  } catch {
    return `${decimals(n, 2)} ${currency}`
  }
}

/** Another of `count` than `previous`, each as likely as the others (`random` in 0..1). */
export function pickAnother(count: number, previous: number | null, random = Math.random): number {
  if (count <= 1 || previous == null || previous < 0 || previous >= count) return Math.floor(random() * Math.max(count, 1))
  const next = Math.floor(random() * (count - 1))
  return next >= previous ? next + 1 : next
}
