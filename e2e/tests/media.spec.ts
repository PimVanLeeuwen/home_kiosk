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

const OVERVIEW = {
  as_of: new Date().toISOString(), stale: false, errors: {}, idle_viewers: 0, genres: ['Drama'],
  viewers: [{ name: 'pim', plays: 49, watch_seconds: 105_334 }],
  library: { movies: 127, shows: 27, episodes: 1564, size_bytes: 4.7e12, added_movies: 0, added_episodes: 8 },
  requests: { pending: 1, processing: 13, available: 0, completed: 58 },
  latest_requests: [{ title: 'VisionQuest', year: '2026', kind: 'tv', by: 'pim', state: 'failed', poster: null }],
}

test('Media adds requests, who watched and the library', async ({ page }) => {
  await page.route('**/api/media', (route) => route.fulfill({ json: MEDIA }))
  await page.route('**/api/media/overview', (route) => route.fulfill({ json: OVERVIEW }))
  await page.goto('/media')

  const requests = page.getByRole('region', { name: 'Requests' })
  await expect(requests).toContainText('waiting for approval')
  await expect(requests).toContainText('VisionQuest')
  await expect(requests).toContainText('Failed')
  await expect(page.getByRole('region', { name: 'Watching · 30 days' })).toContainText('29,3 h')
  await expect(page.getByRole('region', { name: 'Library' })).toContainText('1.564')
})
