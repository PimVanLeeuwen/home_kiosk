import { expect, test } from '@playwright/test'

const PREVIEW = {
  rows: [
    { line: 2, date: '2026-10-02T07:05:00Z', product: 'ASML HOLDING', isin: 'NL0010273215', type: 'BUY', quantity: 1,
      price: 1597, currency: 'EUR', fee: 3, order_id: 'o2', status: 'new', symbol: 'ASML.AS', data_source: 'YAHOO' },
    { line: 3, date: '2024-09-09T13:35:00Z', product: 'NVIDIA CORP', isin: 'US67066G1040', type: 'SELL', quantity: 5,
      price: 104.98, currency: 'USD', fee: 3.5, order_id: 'o1', status: 'exists', symbol: 'NVDA', data_source: 'YAHOO' },
  ],
  skipped: [], unknown: [], accounts: [{ id: 'acc', name: 'DEGIRO' }], account_id: 'acc',
  counts: { new: 1, exists: 1, unknown: 0 },
}

test('DEGIRO export is previewed, then imported', async ({ page }) => {
  const imported: unknown[] = []
  await page.route('**/api/portfolio/degiro/preview', (r) => r.fulfill({ json: PREVIEW }))
  await page.route('**/api/portfolio/degiro/import', (r) => {
    imported.push(r.request().postDataJSON())
    return r.fulfill({ json: { imported: 1, existing: 1, unknown: 0 } })
  })
  await page.goto('/portfolio?import')

  await page.locator('input[type=file]').setInputFiles({
    name: 'Transactions.csv', mimeType: 'text/csv', buffer: Buffer.from('Date,ISIN,Quantity,Price\n'),
  })
  await expect(page.getByText('2 trades in the file')).toBeVisible()
  await page.getByRole('button', { name: 'Import 1 new trade' }).click()
  await expect(page.getByText('Imported 1 trade into Ghostfolio')).toBeVisible()
  expect(imported).toEqual([{ csv: 'Date,ISIN,Quantity,Price\n', account_id: 'acc', choices: {} }])
})
