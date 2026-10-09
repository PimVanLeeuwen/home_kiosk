import { expect, test } from '@playwright/test'

const NAS = {
  as_of: new Date().toISOString(), stale: false, host: 'dev-minotaur', uptime_seconds: 86 * 86_400,
  mem_total_bytes: 7_500_000_000,
  storage: { used_pct: 60, pools: [
    { name: 'volume2', used_bytes: 5.2e12, total_bytes: 6e12, used_pct: 86.9, free_bytes: 0.8e12, projection_months: null },
  ] },
  cpu_pct: 12, ram_pct: 77, cpu_temp_c: 62, containers: { running: 36, total: 36 },
  disks: [{ name: 'sda', temp_c: 42, smart: 'ok' }],
  network: { rx_mbps: 0.1, tx_mbps: 11.6, history: [] },
  backup: { status: 'ok', at: new Date().toISOString() },
}

const HISTORY = [0, 10, 20].map((m) => ({
  t: new Date(Date.now() - (30 - m) * 60_000).toISOString(), cpu: 10 + m, ram: 77, temp: 60, rx_mbps: 1, tx_mbps: 2,
}))

test('the NAS page shows live figures, pools and disks', async ({ page, isMobile }) => {
  await page.route('**/api/nas', (route) => route.fulfill({ json: NAS }))
  await page.route('**/api/nas/history', (route) => route.fulfill({ json: HISTORY }))
  await page.goto('/')

  const nav = isMobile ? page.locator('nav.fixed') : page.locator('aside')
  await nav.getByRole('link', { name: 'NAS' }).click()

  await expect(page.getByText('dev-minotaur · up 86 days')).toBeVisible()
  await expect(page.getByRole('region', { name: 'CPU' }).getByText('Peak 30% in 24 hours')).toBeVisible()
  await expect(page.getByRole('region', { name: 'Storage' }).getByRole('meter', { name: 'volume2' })).toBeVisible()
  await expect(page.getByRole('region', { name: 'Disks' })).toContainText('Healthy')
})

const UPS = {
  as_of: new Date().toISOString(), stale: false, name: 'ups0', model: 'UGREEN US3000', status: 'online',
  status_raw: 'OL', charge: 100, charge_low: 15, load: 1,
  outages: [{ started_at: '2026-10-06T08:02:00Z', ended_at: '2026-10-06T08:41:00Z', lowest_charge: 62, reached_low: false }],
}

test('the NAS page shows the UPS and its last power cut', async ({ page }) => {
  await page.route('**/api/nas', (route) => route.fulfill({ json: NAS }))
  await page.route('**/api/nas/history', (route) => route.fulfill({ json: HISTORY }))
  await page.route('**/api/ups', (route) => route.fulfill({ json: UPS }))
  await page.goto('/nas')

  const card = page.getByRole('region', { name: 'UPS' })
  await expect(card).toContainText('On mains')
  await expect(card.getByRole('meter', { name: 'Battery' })).toBeVisible()
  await expect(card).toContainText('39 min, down to 62%')
})
