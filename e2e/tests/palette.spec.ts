import { expect, test, type Page } from '@playwright/test'

/** As a person would: the shortcut on a computer, the search button on a phone. */
async function openPalette(page: Page, isMobile: boolean) {
  if (isMobile) await page.getByRole('button', { name: 'Search', exact: true }).click()
  else await page.keyboard.press('ControlOrMeta+k')
}

test('the command palette finds a page by a few letters and goes there', async ({ page, isMobile }) => {
  await page.goto('/')

  await openPalette(page, isMobile)

  const palette = page.getByRole('dialog', { name: 'Search the hub' })
  await expect(palette).toBeVisible()
  const field = palette.getByRole('combobox', { name: 'Search' })
  await expect(field).toBeFocused()
  await field.fill('bk')
  await expect(palette.getByRole('option', { selected: true })).toContainText('Backups')
  await field.press('Enter')

  await expect(page).toHaveURL('/backups')
  await expect(palette).toBeHidden()
})

test('the command palette goes to a Settings section and keeps it as recent', async ({ page, isMobile }) => {
  await page.goto('/')
  await openPalette(page, isMobile)
  const palette = page.getByRole('dialog', { name: 'Search the hub' })
  await palette.getByRole('combobox').fill('feeds')
  await palette.getByRole('option', { name: /News feeds/ }).click()
  await expect(page).toHaveURL('/settings/feeds')
  await expect(page.getByRole('heading', { level: 1 })).toHaveText('Settings')

  await openPalette(page, isMobile)
  await expect(palette.getByText('Recent')).toBeVisible()
  await page.keyboard.press('Escape')
  await expect(palette).toBeHidden()
})

test('the command palette opens a service in a new tab, and a container’s logs in Dozzle', async ({ page, context, isMobile }) => {
  const service = (id: string, name: string, port: number) => ({
    id, name, group: 'Apps', description: `${name} app`, port, path: '/', container: id, widget: null, icon: null, status: 'up',
  })
  await page.route('**/api/services', (route) => route.fulfill({ json: {
    as_of: null, stale: false, groups: [{ name: 'Apps', services: [service('paperless', 'Paperless', 8010), service('dozzle', 'Dozzle', 8081)] }],
  } }))
  await page.route('**/api/docker', (route) => route.fulfill({ json: {
    as_of: new Date().toISOString(), stale: false, cpu_pct: 1, mem_bytes: 1,
    containers: [{ name: 'paperless-bridge', project: 'paperless', image: 'x', state: 'running', health: null, status: 'Up', cpu_pct: 0, mem_bytes: 0, mem_limit: null, rx_bps: null, tx_bps: null }],
  } }))
  // The new tab only needs to open: answer it without leaving the test machine.
  await context.route('**:8010/**', (route) => route.fulfill({ body: 'Paperless' }))
  await context.route('**:8081/**', (route) => route.fulfill({ body: 'Dozzle' }))
  await page.goto('/')

  await openPalette(page, isMobile)
  const palette = page.getByRole('dialog', { name: 'Search the hub' })
  await palette.getByRole('combobox').fill('paperl')
  await expect(palette.getByRole('option', { selected: true })).toContainText('Paperless')
  const [tab] = await Promise.all([context.waitForEvent('page'), palette.getByRole('combobox').press('Enter')])
  expect(new URL(tab.url()).port).toBe('8010')
  await tab.close()

  await openPalette(page, isMobile)
  await palette.getByRole('combobox').fill('bridge')
  const [logs] = await Promise.all([context.waitForEvent('page'), palette.getByRole('option', { name: /paperless-bridge/ }).click()])
  expect(logs.url()).toContain(':8081/show?name=paperless-bridge')
})

test('the command palette runs an action through the hub and says it worked', async ({ page, isMobile }) => {
  let sent: unknown = null
  await page.route('**/api/lights/room', (route) => {
    sent = route.request().postDataJSON()
    return route.fulfill({ json: { groups: [] } })
  })
  await page.goto('/')

  await openPalette(page, isMobile)
  const palette = page.getByRole('dialog', { name: 'Search the hub' })
  await expect(palette.getByText('Actions')).toBeVisible()
  await palette.getByRole('combobox').fill('lights off')
  await palette.getByRole('combobox').press('Enter')

  await expect(palette.getByText('The living room lights are off.')).toBeVisible()
  expect(sent).toEqual({ on: false })
  await expect(palette).toBeHidden()
})
