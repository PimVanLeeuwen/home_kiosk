import { expect, test } from '@playwright/test'
import { Shell } from './shell'

const MEDIA = {
  as_of: new Date().toISOString(), stale: false, errors: {},
  downloads: [
    { id: 'sonarr:1', kind: 'tv', title: 'Harbour Lights', detail: 'S2 E5 · The Breakwater', size_bytes: 1.4e9, left_bytes: 3.9e8, progress_pct: 72, time_left_seconds: 372, client: 'SABnzbd', state: 'downloading', message: null, poster: null },
    { id: 'sonarr:2', kind: 'tv', title: 'Northbound', detail: 'S3 E2 · Cold Front', size_bytes: 2.1e9, left_bytes: 1.2e9, progress_pct: 41, time_left_seconds: null, client: 'Transmission', state: 'warning', message: 'The download is stalled with no connections', poster: null },
  ],
  missing: [{ series: 'The Long Coast', season: 1, episode: 5, title: 'Low Water', air_date: new Date(Date.now() - 2 * 86_400_000).toISOString(), poster: null }],
  missing_total: 1,
  upcoming: [],
}

test('Media shows downloads, what needs a look, and missing episodes', async ({ page }) => {
  await page.route('**/api/media', (route) => route.fulfill({ json: MEDIA }))
  await page.goto('/media')
  const shell = new Shell(page)

  await expect(shell.heading()).toHaveText('Media')
  await expect(page.getByText('1 needs a look')).toBeVisible()
  const downloads = page.getByRole('region', { name: 'Downloading' })
  await expect(downloads.getByRole('progressbar', { name: /Harbour Lights/ })).toHaveAttribute('aria-valuenow', '72')
  await expect(downloads).toContainText('The download is stalled with no connections')
  await expect(page.getByRole('region', { name: 'Missing' })).toContainText('aired 2 days ago')
  await expect(page.getByRole('region', { name: 'Next to air' })).toContainText('Nothing airs in the coming week.')
})

test('Media is reachable from the navigation', async ({ page, isMobile }) => {
  await page.route('**/api/media', (route) => route.fulfill({ json: MEDIA }))
  const shell = new Shell(page)
  await page.goto('/')

  if (isMobile) {
    await shell.tabBar.getByRole('link', { name: 'More' }).click()
    await shell.main.getByRole('link', { name: /Media/ }).click()
  } else {
    await shell.sidebar.getByRole('link', { name: 'Media' }).click()
  }
  await expect(page).toHaveURL('/media')
})
