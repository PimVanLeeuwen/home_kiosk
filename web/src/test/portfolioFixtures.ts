import type { HoldingDetail, HoldingRow, Indices, PortfolioFull, PortfolioHistory } from '../lib/portfolioTypes'

const row = (over: Partial<HoldingRow> & Pick<HoldingRow, 'symbol' | 'name' | 'value'>): HoldingRow => ({
  day_pct: 0,
  weight_pct: 0,
  data_source: 'YAHOO',
  isin: null,
  currency: 'EUR',
  quantity: 1,
  price: 1,
  day_abs: 0,
  invested: null,
  gain_abs: null,
  gain_pct: null,
  ...over,
})

export const PORTFOLIO_FULL: PortfolioFull = {
  as_of: '2026-10-02T06:49:00Z',
  stale: false,
  currency: 'EUR',
  total_value: 9143,
  change: { day_abs: -7, day_pct: -0.08, month_pct: 2.1, year_pct: 30.2, all_pct: 103.87 },
  history: [],
  holdings: [
    row({ symbol: 'NVDA', name: 'NVIDIA Corporation', value: 2050, weight_pct: 22.4, day_pct: 1.09, day_abs: 22.11, gain_abs: 1837, gain_pct: 120.62, currency: 'USD' }),
    row({ symbol: 'XDWT.DE', name: 'Xtrackers MSCI World IT', value: 1600, weight_pct: 17.5, day_pct: 0.49, day_abs: 7.88, gain_abs: 715, gain_pct: 80.81 }),
    row({ symbol: 'ASML.AS', name: 'ASML Holding', value: 2100, weight_pct: 23, day_pct: -1.5, day_abs: -32, gain_abs: 950, gain_pct: 82.32 }),
  ],
  allocation: [
    { label: 'Equities', pct: 65.3 },
    { label: 'ETFs', pct: 34.6 },
    { label: 'Cash', pct: 0.1 },
  ],
  invested: 6069,
  gain_abs: 4452,
  cash: 12,
  dividends: 85,
}

export const HISTORY: PortfolioHistory = {
  as_of: '2026-10-02T06:49:00Z',
  stale: false,
  range: 'year',
  points: [
    { d: '2025-10-02', v: 6000, invested: 5000 },
    { d: '2026-04-01', v: 7000, invested: 5500 },
    { d: '2026-10-02', v: 9155, invested: 6069 },
  ],
}

export const INDICES: Indices = {
  as_of: '2026-10-02T06:45:00Z',
  stale: false,
  indices: [
    { symbol: '^GSPC', label: 'S&P 500', currency: 'USD', price: 7666.45, day_pct: 0.19, at: null },
    { symbol: '^AEX', label: 'AEX', currency: 'EUR', price: 1102.63, day_pct: -1.1, at: null },
  ],
}

export const NVDA: HoldingDetail = {
  symbol: 'NVDA',
  data_source: 'YAHOO',
  name: 'NVIDIA Corporation',
  isin: null,
  currency: 'USD',
  quantity: 10,
  average_price: 169.85,
  price: 230.86,
  price_min: 46.57,
  price_max: 240,
  value: 2050,
  invested: 1569,
  gain_abs: 1837,
  gain_pct: 120.62,
  dividends: null,
  fees: 8.02,
  first_activity: '2023-11-06T00:00:00.000Z',
  history: [
    { d: '2023-11-08', price: 46.57 },
    { d: '2026-10-01', price: 230.86 },
  ],
  activities: [
    { date: '2024-09-09T00:00:00.000Z', type: 'SELL', quantity: 5, unit_price: 104.98, fee: 2, currency: 'USD', value: 476 },
    { date: '2023-11-06T00:00:00.000Z', type: 'BUY', quantity: 1, unit_price: 454.91, fee: 2, currency: 'USD', value: 0 },
  ],
}
