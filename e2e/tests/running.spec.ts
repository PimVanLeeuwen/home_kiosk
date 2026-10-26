import { expect, test } from '@playwright/test'

const iso = (d: Date) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
const now = new Date()
const today = iso(now)
// A made-up loop in the North Sea.
const route = Array.from({ length: 50 }, (_, i) => {
  const t = (i / 49) * Math.PI * 2
  return [52.5 + 0.01 * Math.sin(t), 3.5 + 0.016 * Math.cos(t), i ? 300 + 30 * Math.sin(i / 4) : null]
})
const session = {
  uid: 's1', date: today, time: '18:00', name: 'Threshold Intervals', kind: 'Intervals', distance_m: 8300, estimate: '45m - 50m',
  estimate_s: 2850, race: false, steps: ['2km warm up'],
  blocks: [{ kind: 'easy', metres: 2000, seconds: null, pace: null }, { kind: 'work', metres: 800, seconds: null, pace: 255 }],
}
const OVERVIEW = {
  as_of: now.toISOString(), stale: false, has_plan: true,
  last: { id: 'r1', start: new Date(Date.now() - 50 * 3600e3).toISOString(), name: 'Outdoor Run', indoor: false, duration_s: 3248,
    distance_m: 10400, pace_s_per_km: 312, elevation_up_m: 12, avg_hr: 148, max_hr: 171, energy_kcal: 690, temperature_c: 9,
    bests: { '5k': 1421, '10k': 3002, half: null }, route, splits: [], heart: [], session: 'Long Run' },
  week: Array.from({ length: 7 }, (_, i) => {
    const monday = new Date(now.getFullYear(), now.getMonth(), now.getDate() - ((now.getDay() + 6) % 7))
    return { date: iso(new Date(monday.getFullYear(), monday.getMonth(), monday.getDate() + i)), planned_m: 5000, sessions: ['Easy Run'], done_m: 0, routes: [] }
  }),
  totals: { week_m: 0, week_planned_m: 35000, last4_m: 120000, prev4_m: 110000, streak_weeks: 4, runs_this_year: 90, year_m: 900000 },
  bests: { '5k': { seconds: 1421, start: '2026-09-12T07:00:00Z', id: 'a' }, '10k': null, half: null, longest: null },
  next: session, today: { ran: false, session }, race: null,
}

test('Running shows the last run and the next session, and Home has the card on a session day', async ({ page, isMobile }) => {
  await page.route('**/api/runs/overview', (r) => r.fulfill({ json: OVERVIEW }))
  await page.goto('/')

  const card = page.getByRole('region', { name: 'Today: Threshold Intervals' })
  await expect(card).toContainText('8,3 km · 45m - 50m · 18:00')
  if (isMobile) {
    await card.getByRole('link', { name: /Running/ }).click()
  } else {
    await page.locator('aside').getByRole('link', { name: 'Running' }).click()
  }
  await expect(page).toHaveTitle('Running · Home hub')
  await expect(page.getByRole('region', { name: /Last run/ })).toContainText('10,4')
  await expect(page.getByRole('region', { name: 'Next: today, Threshold Intervals' })).toBeVisible()
  await expect(page.getByText('Run today')).toBeVisible()
})

test("Home's streets are fetched in Settings and show under the year, with the runs elsewhere counted", async ({ page }) => {
  let fetched: string | null = null
  const PNG = Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==', 'base64')
  const area = { runs: 88, last: '2026-10-25T07:00:00+00:00', counts: {} }
  await page.route('**/api/runs/streets', (r) => {
    if (r.request().method() === 'POST') fetched = new Date().toISOString()
    const counts = fetched ? { major: 4, minor: 30, path: 10, water: 1, park: 2 } : {}
    return r.fulfill({
      json: {
        areas: [
          { ...area, key: '52.500,3.500', home: true, where: 'home', fetched_at: fetched, counts },
          { ...area, key: '53.300,3.500', home: false, runs: 2, where: 'about 90 km north', fetched_at: null },
        ],
      },
    })
  })
  await page.route('**/api/runs/streets/picture*', (r) => r.fulfill({ body: PNG, contentType: 'image/png' }))
  await page.route('**/api/runs/overview', (r) => r.fulfill({ json: { ...OVERVIEW, streets_at: fetched, runs_elsewhere: 2 } }))

  await page.goto('/settings/running')
  await expect(page.getByText('Elsewhere, about 90 km north')).toBeVisible()
  await page.getByRole('button', { name: 'Fetch the streets: home' }).click()
  await expect(page.getByText(/44 streets and paths, 1 waters, 2 parks/)).toBeVisible()
  await expect(page.getByRole('button', { name: 'Fetch the streets: about 90 km north' })).toBeVisible()

  await page.goto('/running')
  const card = page.getByRole('region', { name: /Your streets/ })
  await expect(card).toContainText('90 runs · 900 km · 2 runs elsewhere')
  await expect(card.getByRole('img')).toBeVisible()
})
