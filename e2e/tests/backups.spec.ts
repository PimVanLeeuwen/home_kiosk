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

const MIRROR = {
  as_of: new Date().toISOString(), stale: false, enabled: true, dir: '/backups/github', error: null,
  owners: [
    { login: 'PimVanLeeuwen', label: 'Mine', removed: [], error: null, repos: [
      { full_name: 'PimVanLeeuwen/home_kiosk', archived: false, ok: true, error: null, mirrored_at: '2026-10-04T00:01:00Z', bytes: 4_200_000 },
    ] },
    { login: 'Hubble-Community-Cafe', label: 'Hubble', removed: [], error: null, repos: [
      { full_name: 'Hubble-Community-Cafe/web', archived: false, ok: false, error: 'fatal: repository not found', mirrored_at: null, bytes: null },
    ] },
  ],
  runs: [{ started: '2026-10-04T00:00:00Z', finished: '2026-10-04T00:02:00Z', ok: false, repos: 2, failed: 1, removed: 0, bytes: 4_200_000 }],
  last_success: null,
  next_due: '2026-10-05T00:00:00Z',
}

test('Backups shows the GitHub mirror and what failed', async ({ page }) => {
  await page.route('**/api/backups', (route) => route.fulfill({ json: HISTORY }))
  await page.route('**/api/github-mirror', (route) => route.fulfill({ json: MIRROR }))
  await page.goto('/backups')

  const card = page.getByRole('region', { name: 'GitHub mirror' })
  await expect(card).toContainText('Mine 1 · Hubble 1 · 1 failed')
  await expect(card).toContainText('Hubble-Community-Cafe/web: fatal: repository not found')
  await card.getByRole('link', { name: /Repos/ }).click()
  await expect(page).toHaveURL(/\/repos$/)
})
