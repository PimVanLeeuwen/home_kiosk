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

const TEMPLATE = {
  id: 'disk_space', group: 'Alert rules', label: 'Disk space', description: 'A storage pool above the threshold.',
  parent: null, category: 'Hub alert rules',
  placeholders: [
    { name: 'level', description: 'The severity', block: false },
    { name: 'pool', description: 'Pool name', block: false },
  ],
  default: '<b>{level}</b> · <b>{pool} is full</b>', text: '<b>{level}</b> · <b>{pool} is full</b>', customised: false,
  preview: '<b>WARNING</b> · <b>volume2 is full</b>',
}

test('rewords a Telegram message in Settings', async ({ page }) => {
  let saved: unknown
  await page.route('**/api/containers', (route) => route.fulfill({ status: 503, json: {} }))
  await page.route('**/api/settings/services', (route) => route.fulfill({ json: CATALOG }))
  await page.route('**/api/settings/feeds', (route) => route.fulfill({ json: [] }))
  await page.route('**/api/alerts/templates', (route) => route.fulfill({ json: [TEMPLATE] }))
  await page.route('**/api/alerts/templates/disk_space/preview', (route) => {
    const { text } = route.request().postDataJSON() as { text: string }
    return route.fulfill({ json: { html: text.replace('{level}', 'WARNING').replace('{pool}', 'volume2'), error: null } })
  })
  await page.route('**/api/alerts/templates/disk_space', (route) => {
    saved = route.request().postDataJSON()
    return route.fulfill({ json: { ...TEMPLATE, text: (saved as { text: string }).text, customised: true } })
  })

  await page.goto('/settings/messages')
  const fold = page.getByRole('button', { name: /Alert rules/ })
  await expect(fold).toHaveText(/1 message/)
  await fold.click()
  await page.getByRole('button', { name: 'Edit Disk space' }).click()
  const form = page.getByRole('form', { name: 'Edit Disk space' })
  await form.getByLabel('Message text').fill('{level} <b>Almost full: </b>')
  await form.getByLabel('Message text').press('End')
  await form.getByRole('button', { name: /\{pool\}/ }).click()
  await expect(form.getByRole('figure', { name: 'Preview' })).toHaveText('WARNING Almost full: volume2')
  await form.getByRole('button', { name: 'Save' }).click()

  await expect(form).toBeHidden()
  await expect(page.getByRole('region', { name: 'Alert rules' })).toContainText('Customised')
  expect(saved).toEqual({ text: '{level} <b>Almost full: </b>{pool}' })
})

test('switches a calendar off in Settings', async ({ page }) => {
  const calendars = [
    { id: 'work-id', name: 'Work', color: '#ff8d28', kind: 'icloud', shown: true },
    { id: 'gewis-id', name: 'GEWIS Activiteiten', color: '#ff6352', kind: 'subscribed', shown: true },
  ]
  await page.route('**/api/settings/calendars', (route) => route.fulfill({ json: calendars }))
  await page.route('**/api/settings/calendars/gewis-id', (route) =>
    route.fulfill({ json: [calendars[0], { ...calendars[1], shown: false }] }))
  await page.goto('/settings/calendars')

  const section = page.getByRole('region', { name: 'Calendars' })
  const gewis = section.getByRole('switch', { name: 'Show GEWIS Activiteiten' })
  await expect(gewis).toHaveAttribute('aria-checked', 'true')
  await gewis.click()
  await expect(gewis).toHaveAttribute('aria-checked', 'false')
})

test('assigns a desk panel board in Settings', async ({ page }) => {
  const seen = new Date(Date.now() - 20_000).toISOString()
  const board = { mac: 'e8:f6:0a:e4:42:b0', panel: null, first_seen: seen, last_seen: seen, firmware: 'a1b2c3d', update_requested: false, key: 'active' }
  let assigned: unknown
  await page.route('**/api/settings/desk-boards', (route) => route.fulfill({ json: [board] }))
  await page.route('**/api/settings/desk-boards/*', (route) => {
    assigned = route.request().postDataJSON()
    return route.fulfill({ json: [{ ...board, panel: 'now' }] })
  })

  await page.goto('/settings/desk-panels')
  const panel = page.getByRole('radiogroup', { name: 'Panel for e8:f6:0a:e4:42:b0' })
  await expect(page.getByText('Online')).toBeVisible()
  await panel.getByRole('radio', { name: 'Now' }).click()

  await expect(panel.getByRole('radio', { name: 'Now' })).toHaveAttribute('aria-checked', 'true')
  expect(assigned).toEqual({ panel: 'now' })
})

test('moves between Settings sections, and old anchors still land on theirs', async ({ page }) => {
  await page.route('**/api/containers', (route) => route.fulfill({ status: 503, json: {} }))
  await page.route('**/api/settings/services', (route) => route.fulfill({ json: CATALOG }))
  await page.route('**/api/settings/calendars', (route) => route.fulfill({ json: [] }))
  await page.route('**/api/settings/desk-boards', (route) => route.fulfill({ json: [] }))

  await page.goto('/settings')
  await expect(page).toHaveURL('/settings/services')
  const nav = page.getByRole('navigation', { name: 'Settings sections' })
  await nav.getByRole('link', { name: 'Calendars' }).click()

  await expect(page).toHaveURL('/settings/calendars')
  await expect(page).toHaveTitle('Calendars · Settings · Home hub')
  await expect(nav.getByRole('link', { name: 'Calendars' })).toHaveAttribute('aria-current', 'page')
  await expect(page.getByRole('region', { name: 'Services' })).toBeHidden()
  await page.reload()
  await expect(page.getByRole('heading', { level: 2, name: 'Calendars' })).toBeVisible()

  await page.goto('/settings#desk-panels')
  await expect(page).toHaveURL('/settings/desk-panels')
  await expect(page.getByRole('heading', { level: 2, name: 'Desk panels' })).toBeVisible()

  // On a phone the chips scroll sideways: the last section's chip is brought into view.
  await page.route('**/api/alerts/templates', (route) => route.fulfill({ json: [] }))
  await page.goto('/settings/messages')
  await expect(nav.getByRole('link', { name: 'Messages' })).toBeInViewport()
})

test('asks a desk panel board to update now', async ({ page }) => {
  const seen = new Date(Date.now() - 20_000).toISOString()
  const board = { mac: 'e8:f6:0a:e4:42:c8', panel: 'home', first_seen: seen, last_seen: seen, firmware: 'a1b2c3d', update_requested: false, key: 'active' }
  let asked = false
  await page.route('**/api/settings/desk-boards', (route) => route.fulfill({ json: [board] }))
  await page.route('**/panels/firmware.json', (route) => route.fulfill({ json: { version: '2ca91f6', size: 1720928 } }))
  await page.route('**/api/settings/desk-boards/*/update', (route) => {
    asked = route.request().method() === 'POST'
    return route.fulfill({ json: [{ ...board, update_requested: true }] })
  })

  await page.goto('/settings#desk-panels')
  await page.getByRole('button', { name: 'Update to 2ca91f6' }).click()

  await expect(page.getByRole('status').filter({ hasText: 'Updating to 2ca91f6' })).toBeVisible()
  expect(asked).toBe(true)
})

test('Settings shows the AI spend against its cap', async ({ page }) => {
  await page.route('**/api/ai', (route) => route.fulfill({ json: {
    as_of: new Date().toISOString(), stale: false, configured: true, cap: 5, spent: 0.42, calls: 31, capped: false, features: [],
  } }))
  await page.goto('/settings/ai')

  await expect(page.getByRole('heading', { name: 'AI', level: 2 })).toBeVisible()
  await expect(page.getByText('0.42 of 5.00 · 31 calls')).toBeVisible()
  await expect(page.getByRole('meter', { name: 'Spent this month' })).toBeVisible()
})
