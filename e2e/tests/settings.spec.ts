import { expect, test } from '@playwright/test'

const svc = (id: string, name: string, group: string, port: number) => ({
  id, name, group, description: '', port, path: '/', container: id, widget: null,
})

const CATALOG = {
  services: [svc('jellyfin', 'Jellyfin', 'Media', 8096), svc('sonarr', 'Sonarr', 'Arr', 8989)],
  widgets: ['jellyfin', 'sonarr'],
}

test('adds a service from Settings', async ({ page }) => {
  let posted: unknown
  await page.route('**/api/containers', (route) => route.fulfill({ status: 503, json: {} }))
  await page.route('**/api/settings/services', async (route) => {
    if (route.request().method() === 'POST') {
      posted = route.request().postDataJSON()
      expect(route.request().headers()['content-type']).toContain('application/json')
      return route.fulfill({
        status: 201,
        json: { ...CATALOG, services: [...CATALOG.services, svc('uptime-kuma', 'Uptime Kuma', 'Monitoring', 3001)] },
      })
    }
    return route.fulfill({ json: CATALOG })
  })

  await page.goto('/settings')
  await page.getByRole('button', { name: 'Add service' }).click()
  const form = page.getByRole('form', { name: 'Add a service' })
  await form.getByLabel('Name').fill('Uptime Kuma')
  await form.getByLabel('Group').fill('Monitoring')
  await form.getByLabel('Port').fill('3001')
  await form.getByRole('button', { name: 'Add service' }).click()

  await expect(page.getByRole('region', { name: 'Monitoring' })).toContainText('Uptime Kuma')
  await expect(form).toBeHidden()
  expect(posted).toMatchObject({ name: 'Uptime Kuma', group: 'Monitoring', port: 3001 })
})

test('reorders with the move buttons', async ({ page }) => {
  let order: unknown
  await page.route('**/api/containers', (route) => route.fulfill({ status: 503, json: {} }))
  await page.route('**/api/settings/services', (route) => route.fulfill({ json: CATALOG }))
  await page.route('**/api/settings/services-order', (route) => {
    order = route.request().postDataJSON()
    return route.fulfill({ json: { ...CATALOG, services: [...CATALOG.services].reverse() } })
  })

  await page.goto('/settings')
  await page.getByRole('button', { name: 'Move group Arr up' }).click()

  await expect(page.getByRole('heading', { level: 3 })).toHaveText(['Arr', 'Media'])
  expect(order).toEqual({ ids: ['sonarr', 'jellyfin'] })
})
