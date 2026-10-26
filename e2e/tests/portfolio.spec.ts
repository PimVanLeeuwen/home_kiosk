import { expect, test } from '@playwright/test'

const PORTFOLIO = {
  as_of: new Date().toISOString(), stale: false, currency: 'EUR', total_value: 9143,
  change: { day_abs: -7, day_pct: -0.08, month_pct: 2, year_pct: 30, all_pct: 103.87 }, history: [],
  holdings: [{ symbol: 'NVDA', name: 'NVIDIA Corporation', value: 2050, day_pct: 1.09, weight_pct: 22.4, data_source: 'YAHOO',
    isin: null, currency: 'USD', quantity: 10, price: 230.86, day_abs: 22.11, invested: 1569, gain_abs: 1837, gain_pct: 120.62 }],
  allocation: [{ label: 'Equities', pct: 100 }], invested: 6069, gain_abs: 4452, cash: 12, dividends: 0,
}
const HISTORY = { as_of: PORTFOLIO.as_of, stale: false, range: 'year', points: [
  { d: '2025-10-02', v: 6000, invested: 5000 }, { d: '2026-10-02', v: 9155, invested: 6069 },
] }
const NVDA = {
  symbol: 'NVDA', data_source: 'YAHOO', name: 'NVIDIA Corporation', isin: null, currency: 'USD', quantity: 10,
  average_price: 169.85, price: 230.86, price_min: 46, price_max: 240, value: 2050, invested: 1569, gain_abs: 1837,
  gain_pct: 120.62, dividends: null, fees: 8, first_activity: '2023-11-06T00:00:00.000Z',
  history: [{ d: '2023-11-08', price: 46.57 }, { d: '2026-10-01', price: 230.86 }],
  activities: [{ date: '2024-09-09T00:00:00.000Z', type: 'SELL', quantity: 5, unit_price: 104.98, fee: 2, currency: 'USD', value: 476 }],
}

test('Portfolio shows the summary and opens a holding', async ({ page }) => {
  await page.route('**/api/portfolio', (r) => r.fulfill({ json: PORTFOLIO }))
  await page.route('**/api/portfolio/history?**', (r) => r.fulfill({ json: HISTORY }))
  await page.route('**/api/indices', (r) => r.fulfill({ json: { as_of: PORTFOLIO.as_of, stale: false, indices: [] } }))
  await page.route('**/api/portfolio/holdings/YAHOO/NVDA', (r) => r.fulfill({ json: NVDA }))
  await page.goto('/portfolio')

  await expect(page.getByRole('region', { name: 'Value' })).toContainText('€ 9.143')
  await expect(page.getByRole('region', { name: 'Summary' })).toContainText('Total gain')
  await expect(page.getByRole('img', { name: /Portfolio value, 1Y/ })).toBeVisible()
  // The heat map's tile and the holdings row both open the holding.
  await expect(page.getByRole('region', { name: "Today's movers" }).getByRole('link', { name: /^NVDA, / }).filter({ visible: true })).toHaveAttribute('href', '/portfolio?h=YAHOO%2FNVDA')
  await page.getByRole('region', { name: /^Holdings/ }).getByRole('link', { name: /NVDA/ }).filter({ visible: true }).click()

  await expect(page).toHaveURL('/portfolio?h=YAHOO%2FNVDA')
  await expect(page.getByRole('heading', { name: 'NVDA', level: 1 })).toBeVisible()
  await expect(page.getByRole('region', { name: 'Transactions' })).toContainText('Sell')
  await page.getByRole('main').getByRole('link', { name: 'Portfolio' }).click()
  await expect(page).toHaveURL('/portfolio')
})

for (const reduced of [false, true]) {
  test(`The chart ${reduced ? 'stays still with reduced motion' : 'draws in once on load'}`, async ({ browser }) => {
    const context = await browser.newContext({ reducedMotion: reduced ? 'reduce' : 'no-preference', serviceWorkers: 'block' })
    const page = await context.newPage()
    await page.route('**/api/portfolio', (r) => r.fulfill({ json: PORTFOLIO }))
    await page.route('**/api/portfolio/history?**', (r) => r.fulfill({ json: HISTORY }))
    await page.route('**/api/indices', (r) => r.fulfill({ json: { as_of: PORTFOLIO.as_of, stale: false, indices: [] } }))
    await page.goto('/portfolio')
    await expect(page.getByRole('img', { name: /Portfolio value, 1Y/ })).toBeVisible()

    const names = await page.evaluate(() => document.getAnimations().map((a) => (a as CSSAnimation).animationName))
    if (reduced) expect(names.filter((n) => ['reveal', 'fill-in', 'sweep', 'grow', 'grow-x'].includes(n))).toEqual([])
    else expect(names).toEqual(expect.arrayContaining(['reveal', 'sweep']))
    await context.close()
  })
}
