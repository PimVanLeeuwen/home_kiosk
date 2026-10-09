import { expect, test } from '@playwright/test'

// The service worker is blocked in the other specs (playwright.config.ts).
test.use({ serviceWorkers: 'allow' })

test('the hub is installable: a manifest with icons', async ({ page, request }) => {
  await page.goto('/')
  const href = await page.locator('link[rel="manifest"]').getAttribute('href')
  expect(href).toBe('/manifest.webmanifest')

  const manifest = await request.get(href!)
  expect(manifest.ok()).toBe(true)
  const body = await manifest.json()
  expect(body).toMatchObject({ name: 'Home hub', start_url: '/', scope: '/', display: 'standalone' })
  for (const icon of body.icons) {
    const file = await request.get(icon.src)
    expect(file.ok(), icon.src).toBe(true)
    expect(file.headers()['content-type']).toBe('image/png')
  }
  expect(body.icons.map((i: { purpose: string }) => i.purpose)).toContain('maskable')
})

test('it opens without the hub, showing the last data as stale', async ({ page, context }) => {
  const at = (minutes: number) => new Date(Date.now() + minutes * 60_000).toISOString()
  // context.route also sees the service worker's own requests.
  await context.route('**/api/weather', (route) => route.fulfill({ json: {
    as_of: at(0), stale: false, station: 'Meetstation De Bilt', measured_at: at(-15),
    description: 'Licht bewolkt', temperature: 15.2, feel_temperature: 14, wind_bft: 2, wind_direction: 'W',
    humidity: 70, rain_last_hour: 0, sunrise: at(-400), sunset: at(240),
    rain: Array.from({ length: 24 }, (_, i) => ({ at: at(i * 5), mm_per_hour: 0 })),
  } }))

  await page.goto('/')
  await page.waitForFunction(async () => (await navigator.serviceWorker.ready).active !== null)
  // Once the worker controls the page, the data passes through it and is kept.
  await page.reload()
  await expect(page.getByRole('region', { name: 'Weather' })).toContainText('15 °C')

  // A mocked route answers even offline, so drop it: the hub is now really gone.
  await context.unroute('**/api/weather')
  await context.setOffline(true)
  await page.reload()

  const weather = page.getByRole('region', { name: 'Weather' })
  await expect(weather).toContainText('15 °C')
  await expect(weather).toContainText('Showing the last known figures.')
  await context.setOffline(false)
})

test('the kiosk is left to the network', async ({ page, context }) => {
  await page.goto('/')
  await page.waitForFunction(async () => (await navigator.serviceWorker.ready).active !== null)
  await page.goto('/kiosk/')
  await context.setOffline(true)
  const reload = await page.reload().catch((error: Error) => error)
  expect(reload).toBeInstanceOf(Error)
  await context.setOffline(false)
})
