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
