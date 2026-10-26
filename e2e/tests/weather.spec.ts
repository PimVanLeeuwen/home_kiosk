import { expect, test } from '@playwright/test'

const iso = (d: Date) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
const now = new Date()
const at = (minutes: number) => new Date(Date.now() + minutes * 60_000).toISOString()
const days = Array.from({ length: 7 }, (_, n) => ({
  date: iso(new Date(now.getFullYear(), now.getMonth(), now.getDate() + n)),
  high: 12 + n, low: 6, sunrise: '07:31', sunset: '17:22', code: n === 0 ? 61 : 2, rain_max: n === 0 ? 70 : 10,
  hours: Array.from({ length: 24 }, (_, h) => ({ hour: h, temperature: h > 7 && h < 19 ? 12 : 7, rain_chance: h === 18 ? 70 : 0 })),
}))
// A tiny made-up picture: a 1 x 1 PNG.
const PNG = Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==', 'base64')

test('Weather opens from the Home card with today, the week and the radar', async ({ page }) => {
  await page.route('**/api/weather', (r) => r.fulfill({ json: {
    as_of: at(0), stale: false, station: 'Meetstation De Bilt', measured_at: at(-10), description: 'Regen',
    temperature: 11.4, feel_temperature: 9.8, wind_bft: 4, wind_direction: 'ZW', humidity: 90, rain_last_hour: 0.4,
    sunrise: at(-300), sunset: at(240), rain: Array.from({ length: 24 }, (_, i) => ({ at: at(i * 5), mm_per_hour: i > 4 ? 1.2 : 0 })),
  } }))
  await page.route('**/api/forecast', (r) => r.fulfill({ json: { as_of: at(0), stale: false, days } }))
  await page.route('**/api/radar', (r) => r.fulfill({ json: { as_of: at(0), stale: false, stamp: '202610261205', wet: true, home: [281, 312] } }))
  await page.route('**/api/radar/map*', (r) => r.fulfill({ body: PNG, contentType: 'image/png' }))
  await page.goto('/')

  await page.getByRole('region', { name: 'Weather' }).getByRole('link', { name: /Week and radar/ }).click()
  await expect(page).toHaveTitle('Weather · Home hub')
  await expect(page.getByText('Rain on the way')).toBeVisible()
  await expect(page.getByRole('region', { name: 'Today' }).getByRole('img', { name: /rain most likely around 18:00/ })).toBeVisible()
  await expect(page.getByRole('region', { name: 'The week' }).getByRole('listitem')).toHaveCount(7)
  await expect(page.getByRole('region', { name: 'Rain radar' }).getByRole('img', { name: /The rain radar round home/ })).toBeVisible()
})
