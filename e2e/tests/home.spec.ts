import { expect, test } from '@playwright/test'

const NAS = {
  as_of: new Date().toISOString(),
  stale: false,
  host: 'dev-minotaur',
  storage: {
    used_pct: 70,
    pools: [{ name: 'volume2', used_bytes: 5.9e12, total_bytes: 6e12, used_pct: 98.5, free_bytes: 8.7e10 }],
  },
  cpu_pct: 11,
  ram_pct: 24,
  cpu_temp_c: 44,
  containers: { running: 37, total: 37 },
  disks: [{ name: 'sda', temp_c: 35, smart: 'ok' }],
  network: { rx_mbps: 19.2, tx_mbps: 2.4 },
  backup: { status: 'ok', at: new Date().toISOString() },
}

const SERVICES = {
  as_of: new Date().toISOString(),
  stale: false,
  groups: [{ name: 'Media', services: [
    { id: 'jellyfin', name: 'Jellyfin', group: 'Media', description: 'Media server', port: 8096, path: '/', container: 'jellyfin', widget: 'jellyfin', status: 'up', stats: [{ label: 'Streaming', value: 2, unit: 'count' }], stats_error: null },
  ] }],
}

test('Home brings status, cards and services together', async ({ page }) => {
  await page.route('**/api/nas', (route) => route.fulfill({ json: NAS }))
  await page.route('**/api/services', (route) => route.fulfill({ json: SERVICES }))
  // Portfolio and news left unstubbed: the e2e stack has no collector (502).
  await page.goto('/')

  await expect(page).toHaveTitle('Home · Home hub')
  await expect(page.getByText(/1 thing needs a look/)).toBeVisible()
  await expect(page.getByText('volume2 98% full')).toBeVisible()
  await expect(page.getByRole('region', { name: 'Portfolio' })).toContainText('not available right now')
  await expect(page.getByRole('region', { name: 'Services' }).getByRole('link', { name: /Jellyfin/ })).toContainText('2 streaming')
  await expect(page.getByRole('region', { name: 'NAS' }).getByRole('meter', { name: 'volume2' })).toBeVisible()
})
