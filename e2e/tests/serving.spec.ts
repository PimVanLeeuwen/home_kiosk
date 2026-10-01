import { expect, test } from '@playwright/test'

test('the kiosk carousel is served under /kiosk/', async ({ page }) => {
  // Without ?data=api the carousel renders its bundled fixtures.
  await page.goto('/kiosk')

  await expect(page).toHaveURL('/kiosk/')
  await expect(page).toHaveTitle('Desk dashboard')
  await expect(page.getByText('Total value')).toBeVisible()
})

test('the old reading view address redirects into /kiosk/', async ({ page }) => {
  await page.goto('/read.html')

  await expect(page).toHaveURL('/kiosk/read.html')
  await expect(page).toHaveTitle('Headlines')
})

test('development files are not served', async ({ request }) => {
  for (const path of ['/kiosk/Dockerfile', '/kiosk/serve.py']) {
    expect((await request.get(path)).status(), path).toBe(404)
  }
})

test('pages revalidate while hashed assets cache for good', async ({ page, request }) => {
  for (const path of ['/', '/alerts']) {
    expect((await request.get(path)).headers()['cache-control'], path).toBe('no-cache')
  }

  await page.goto('/')
  const script = await page.locator('script[type="module"]').getAttribute('src')
  const asset = await request.get(script!)
  expect(asset.headers()['cache-control']).toContain('immutable')
})

test('the favicon is served and linked from the hub and the kiosk', async ({ page, request }) => {
  for (const [path, type] of [
    ['/favicon.svg', 'image/svg+xml'],
    ['/favicon-32.png', 'image/png'],
    ['/apple-touch-icon.png', 'image/png'],
  ]) {
    const response = await request.get(path)
    expect(response.status(), path).toBe(200)
    expect(response.headers()['content-type'], path).toContain(type)
  }

  await page.goto('/')
  await expect(page.locator('link[rel="icon"][type="image/svg+xml"]')).toHaveAttribute('href', '/favicon.svg')
  await page.goto('/kiosk/')
  await expect(page.locator('link[rel="icon"]')).toHaveAttribute('href', '/favicon.svg')
})
