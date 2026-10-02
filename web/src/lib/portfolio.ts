/** A holding's detail lives at /portfolio?h=<dataSource>/<symbol>. */
export function holdingPath(h: { data_source: string | null; symbol: string }): string {
  return `/portfolio?h=${encodeURIComponent(`${h.data_source ?? 'YAHOO'}/${h.symbol}`)}`
}

/** The `h` parameter back into its parts; null when it is not one. */
export function parseHolding(param: string | null): { dataSource: string; symbol: string } | null {
  const match = param?.match(/^([A-Z_]+)\/(.+)$/)
  return match ? { dataSource: match[1], symbol: match[2] } : null
}
