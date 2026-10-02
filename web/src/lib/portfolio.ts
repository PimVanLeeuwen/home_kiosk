/** A holding's detail lives at /portfolio?h=<dataSource>/<symbol>. */
export function holdingPath(h: { data_source: string | null; symbol: string }): string {
  return `/portfolio?h=${encodeURIComponent(`${h.data_source ?? 'YAHOO'}/${h.symbol}`)}`
}

/** The `h` parameter back into its parts; null when it is not one. */
export function parseHolding(param: string | null): { dataSource: string; symbol: string } | null {
  const match = param?.match(/^([A-Z_]+)\/(.+)$/)
  return match ? { dataSource: match[1], symbol: match[2] } : null
}

/**
 * Today's move as the sum of the holdings' moves, as the collector's moves.py
 * does for the report and the bot. Falls back to Ghostfolio's own figure when
 * the holdings carry no move in euros.
 */
export function dayMove(p: {
  total_value: number
  change: { day_abs: number; day_pct: number }
  holdings: { day_abs?: number | null }[]
}): { abs: number; pct: number } {
  if (!p.holdings.length || p.holdings.some((h) => h.day_abs == null))
    return { abs: p.change.day_abs, pct: p.change.day_pct }
  const abs = p.holdings.reduce((sum, h) => sum + (h.day_abs ?? 0), 0)
  const before = p.total_value - abs
  return { abs, pct: before ? (abs / before) * 100 : 0 }
}
