import { expect, test } from '@playwright/test'

const vol = (name: string, ok = true) => ({
  name, ok, exit_code: ok ? 0 : 7, seconds: name === 'volume1' ? 241 : 1140, bytes: ok ? 500_000_000 : 10,
  transfers: 12, checks: 5120, deletes: 0, errors: ok ? 0 : 1, last_error: ok ? null : 'quota exceeded',
})
const run = (day: number, ok = true) => ({
  started: `2026-09-${day}T01:00:00Z`, finished: `2026-09-${day}T01:23:00Z`, ok,
  volumes: [vol('volume1'), vol('volume3', ok)],
})
const HISTORY = {
  as_of: new Date().toISOString(), stale: false,
  runs: [run(28, false), run(27), run(26)],
  volumes: [
    { name: 'volume1', last_run: run(28, false), last_success: '2026-09-28T01:23:00Z' },
    { name: 'volume3', last_run: run(28, false), last_success: '2026-09-27T01:23:00Z' },
  ],
  next_due: '2026-09-29T01:23:00Z',
}

test('Backups shows per-volume results and the run history', async ({ page }) => {
  await page.route('**/api/backups', (route) => route.fulfill({ json: HISTORY }))
  await page.goto('/backups')

  await expect(page.getByRole('region', { name: 'volume3' })).toContainText('quota exceeded')
  await expect(page.getByRole('img', { name: 'Duration of the last 3 runs; 1 failed.' })).toBeVisible()
  await expect(page.getByRole('region', { name: 'Last 3 runs' }).getByRole('row')).toHaveCount(4)
})
