/** Shapes of the Portfolio page endpoints (collector app/portfolio). */
import type { Portfolio } from './types'

export interface HoldingRow {
  symbol: string
  name: string
  value: number
  day_pct: number
  weight_pct: number
  data_source: string | null
  isin: string | null
  currency: string | null
  quantity: number | null
  price: number | null
  day_abs: number | null
  invested: number | null
  gain_abs: number | null
  gain_pct: number | null
}

/** /api/portfolio with the Home hub additions. */
export interface PortfolioFull extends Omit<Portfolio, 'holdings'> {
  holdings: HoldingRow[]
  allocation: { label: string; pct: number }[]
  invested: number | null
  gain_abs: number | null
  cash: number | null
  dividends: number | null
}

export type ChartRange = 'month' | 'ytd' | 'year' | 'max'

export interface PortfolioHistory {
  as_of: string
  stale: boolean
  range: ChartRange
  points: { d: string; v: number; invested: number | null }[]
}

export interface HoldingDetail {
  symbol: string
  data_source: string
  name: string
  isin: string | null
  currency: string | null
  quantity: number
  average_price: number
  price: number
  price_min: number | null
  price_max: number | null
  value: number
  invested: number | null
  gain_abs: number | null
  gain_pct: number | null
  dividends: number | null
  fees: number | null
  first_activity: string | null
  history: { d: string; price: number }[]
  activities: {
    date: string
    type: string
    quantity: number
    unit_price: number
    fee: number
    currency: string
    value: number | null
  }[]
}

export interface Indices {
  as_of: string
  stale: boolean
  indices: { symbol: string; label: string; currency: string | null; price: number; day_pct: number; at: string | null }[]
}

export interface DegiroCandidate {
  symbol: string
  data_source: string
  name: string
  currency: string | null
  held: boolean
}

export interface DegiroRow {
  line: number
  date: string
  product: string
  isin: string
  type: 'BUY' | 'SELL'
  quantity: number
  price: number
  currency: string
  fee: number
  order_id: string
  status: 'new' | 'exists' | 'unknown'
  symbol: string | null
  data_source: string | null
}

export interface DegiroPreview {
  rows: DegiroRow[]
  skipped: string[]
  unknown: { isin: string; product: string; candidates: DegiroCandidate[] }[]
  accounts: { id: string; name: string }[]
  account_id: string | null
  counts: { new: number; exists: number; unknown: number }
}

export type DegiroChoices = Record<string, { data_source: string; symbol: string }>
