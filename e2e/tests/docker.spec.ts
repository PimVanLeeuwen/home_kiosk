import { expect, test } from '@playwright/test'

const c = (name: string, project: string, over: Record<string, unknown> = {}) => ({
  name, project, image: `${name}:latest`, state: 'running', health: null, status: 'Up 2 days',
  cpu_pct: 1, mem_bytes: 200_000_000, mem_limit: 8_000_000_000, rx_bps: 1000, tx_bps: 100, ...over,
})

const OVERVIEW = {
  as_of: new Date().toISOString(),
  stale: false,
  cpu_pct: 13.5,
  mem_bytes: 1_300_000_000,
  containers: [c('jellyfin', 'jellyfin', { cpu_pct: 12.5 }), c('sonarr', 'sonarr'), c('transmission', 'qbittorrent', { state: 'exited', cpu_pct: null, mem_bytes: null })],
}

test('Docker shows containers by stack and opens one for its history', async ({ page }) => {
  await page.route('**/api/docker', (route) => route.fulfill({ json: OVERVIEW }))
  await page.route('**/api/docker/sparklines', (route) => route.fulfill({ json: {} }))
  await page.route('**/api/docker/updates', (route) => route.fulfill({ json: [] }))
  await page.route('**/api/docker/history/jellyfin', (route) =>
    route.fulfill({ json: [
      { t: '2026-10-01T10:00:00Z', cpu: 3, mem: 800_000_000 },
      { t: '2026-10-01T10:10:00Z', cpu: 12.5, mem: 900_000_000 },
    ] }),
  )
  await page.goto('/docker')

  await expect(page.getByText('2 of 3 running')).toBeVisible()
  await expect(page.getByRole('region', { name: 'qbittorrent · 0/1' })).toBeVisible()

  await page.getByRole('button', { name: /jellyfin/ }).click()
  await expect(page.getByRole('img', { name: 'jellyfin memory, last 24 hours' })).toBeVisible()
  await expect(page.getByText(/No updates seen yet/)).toBeVisible()
})
