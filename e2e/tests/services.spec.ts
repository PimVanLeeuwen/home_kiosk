import { expect, test } from '@playwright/test'
import { Shell } from './shell'

const SERVICES = {
  as_of: '2026-09-30T12:00:00Z',
  stale: false,
  groups: [
    {
      name: 'Media',
      services: [
        { id: 'jellyfin', name: 'Jellyfin', group: 'Media', description: 'Media server', port: 8096, path: '/', container: 'jellyfin', widget: 'jellyfin', status: 'up' },
        { id: 'immich', name: 'Immich', group: 'Media', description: 'Photos', port: 2283, path: '/', container: 'immich_server', widget: 'immich', status: 'unhealthy' },
      ],
    },
    {
      name: 'Apps',
      services: [
        { id: 'couchdb', name: 'CouchDB', group: 'Apps', description: 'Obsidian LiveSync', port: 5984, path: '/_utils', container: 'couchdb', widget: null, status: 'up' },
      ],
    },
  ],
}

const HOSTS = {
  as_of: '2026-09-30T12:00:00Z',
  stale: false,
  lan: '192.168.1.10',
  tailscale: { dns_name: 'dev-minotaur.tail1234.ts.net', ip: '100.70.0.10' },
}

test('lists services by group with status and links to the NAS', async ({ page }) => {
  await page.route('**/api/services', (route) => route.fulfill({ json: SERVICES }))
  await page.route('**/api/hosts', (route) => route.fulfill({ json: HOSTS }))
  const shell = new Shell(page)
  await page.goto('/services')

  await expect(shell.heading()).toHaveText('Services')
  await expect(page.getByText('2 of 3 running')).toBeVisible()
  const media = page.getByRole('region', { name: 'Media' })
  await expect(media.getByRole('link')).toHaveCount(2)
  await expect(media.getByRole('link', { name: /Immich/ })).toHaveAccessibleName(/Unhealthy/)

  // The test server is localhost, so links use the NAS LAN address.
  await expect(page.getByRole('link', { name: /CouchDB/ })).toHaveAttribute(
    'href',
    'http://192.168.1.10:5984/_utils',
  )
})

test('shows a retry when the collector is down', async ({ page }) => {
  // No stub: the e2e stack has no collector, so Caddy answers 502.
  await page.goto('/services')

  await expect(page.getByRole('alert')).toContainText('The hub API is not answering')
  await expect(page.getByRole('button', { name: 'Try again' })).toBeVisible()
})
