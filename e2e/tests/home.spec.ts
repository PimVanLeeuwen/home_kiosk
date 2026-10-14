import { expect, test } from '@playwright/test'

const NAS = {
  as_of: new Date().toISOString(),
  stale: false,
  host: 'dev-minotaur',
  storage: {
    used_pct: 70,
    pools: [{ name: 'volume2', used_bytes: 5.9e12, total_bytes: 6e12, used_pct: 98.5, free_bytes: 8.7e10 }],
  },
  cpu_pct: 11,
  ram_pct: 24,
  cpu_temp_c: 44,
  containers: { running: 37, total: 37 },
  disks: [{ name: 'sda', temp_c: 35, smart: 'ok' }],
  network: { rx_mbps: 19.2, tx_mbps: 2.4 },
  backup: { status: 'ok', at: new Date().toISOString() },
}

const SERVICES = {
  as_of: new Date().toISOString(),
  stale: false,
  groups: [{ name: 'Media', services: [
    { id: 'jellyfin', name: 'Jellyfin', group: 'Media', description: 'Media server', port: 8096, path: '/', container: 'jellyfin', widget: 'jellyfin', status: 'up', stats: [{ label: 'Streaming', value: 2, unit: 'count' }], stats_error: null },
  ] }],
}

test('Home brings status, cards and services together', async ({ page }) => {
  await page.route('**/api/nas', (route) => route.fulfill({ json: NAS }))
  await page.route('**/api/services', (route) => route.fulfill({ json: SERVICES }))
  // Portfolio and news left unstubbed: the e2e stack has no collector (502).
  await page.goto('/')

  await expect(page).toHaveTitle('Home · Home hub')
  await expect(page.getByText(/1 thing needs a look/)).toBeVisible()
  await expect(page.getByText('volume2 98% full')).toBeVisible()
  await expect(page.getByRole('region', { name: 'Portfolio' })).toContainText('not available right now')
  await expect(page.getByRole('region', { name: 'Services' }).getByRole('link', { name: /Jellyfin/ })).toContainText('2 streaming')
  await expect(page.getByRole('region', { name: 'NAS' }).getByRole('meter', { name: 'volume2' })).toBeVisible()
})

test('Home shows the weather with the rain in the next two hours', async ({ page }) => {
  const at = (minutes: number) => new Date(Date.now() + minutes * 60_000).toISOString()
  await page.route('**/api/weather', (route) => route.fulfill({ json: {
    as_of: at(0), stale: false, station: 'Meetstation De Bilt', measured_at: at(-15),
    description: 'Zwaar bewolkt', temperature: 12.9, feel_temperature: 10.6, wind_bft: 4, wind_direction: 'ZW',
    humidity: 94, rain_last_hour: 0, sunrise: at(-400), sunset: at(240),
    rain: Array.from({ length: 24 }, (_, i) => ({ at: at(i * 5), mm_per_hour: 0 })),
  } }))
  await page.goto('/')

  const card = page.getByRole('region', { name: 'Weather' })
  const ring = card.getByRole('img', { name: 'Dry for the next 2 hours' })
  await expect(ring).toBeVisible()
  await expect(ring).toContainText('13°')
  await expect(card.getByRole('link', { name: 'Buienradar' })).toBeVisible()
})

// A weekday morning: the train card sits at the top of Home until the train leaves.
const MORNING = new Date(2026, 9, 14, 6, 42)
const at = (h: number, m: number) => new Date(2026, 9, 14, h, m).toISOString()
const stop = (name: string, h: number, m: number, track: string) => ({ name, planned: at(h, m), actual: at(h, m), track, cancelled: false })
const TRAIN = {
  as_of: MORNING.toISOString(), stale: false, date: '2026-10-14', route: 'Leiden Centraal to Rotterdam Centraal',
  departure: '07:16', mode: 'morning', watching: true, departed: false, next_direct: null,
  disruptions: [{ id: 'w1', kind: 'MAINTENANCE', title: 'Utrecht - Amsterdam.', text: 'Minder treinen.', until: null }],
  train: {
    name: 'IC 3522', status: 'on_time', planned_departure: at(7, 16), actual_departure: at(7, 16), delay_minutes: 0,
    planned_track: '6', actual_track: '4',
    stops: [stop('Leiden Centraal', 7, 16, '4'), stop("Den Haag HS", 7, 39, '3'), stop('Delft', 8, 11, '7'), stop('Rotterdam Centraal', 8, 28, '2')],
  },
}

test('Home shows the morning train at the top until it leaves', async ({ page }) => {
  await page.clock.install({ time: MORNING })
  await page.route('**/api/train', (route) => route.fulfill({ json: TRAIN }))
  await page.goto('/')

  const card = page.getByRole('region', { name: /^Your train/ })
  await expect(card).toContainText('On time')
  await expect(card).toContainText('Leaves in 34 min from platform')
  await expect(card.getByRole('img', { name: '34 min to go' })).toBeVisible()
  await expect(card.getByRole('list', { name: 'Stops' }).getByRole('listitem')).toHaveCount(4)
  await expect(card.getByRole('note')).toContainText('Utrecht - Amsterdam.')

  await page.unroute('**/api/train')
  await page.route('**/api/train', (route) => route.fulfill({ json: { ...TRAIN, watching: false, departed: true } }))
  await page.reload()
  await expect(page.getByRole('heading', { level: 1 })).toBeVisible()
  await expect(page.getByRole('region', { name: /^Your train/ })).toHaveCount(0)
})

const CAL_AT = (h: number, m = 0) => new Date(2026, 9, 14, h, m).toISOString()
const TODAY = {
  as_of: CAL_AT(9), stale: false, date: '2026-10-14', errors: {},
  events: [
    { calendar_id: 'w', calendar: 'Work', color: '#5aa9ff', title: 'Standup', start: CAL_AT(9, 30), end: CAL_AT(10), all_day: false },
    { calendar_id: 'f', calendar: 'Family', color: '#c8a0ff', title: 'Lunch with Sanne', start: CAL_AT(12, 30), end: CAL_AT(13, 30), all_day: false },
  ],
  all_day: [{ calendar_id: 'b', calendar: 'Birthdays', color: '#ff8fa3', title: "Mama's birthday", start: null, end: null, all_day: true }],
}

test("Home shows today's calendar with the next event first", async ({ page }) => {
  await page.clock.install({ time: new Date(2026, 9, 14, 9, 6) })
  await page.route('**/api/calendar', (route) => route.fulfill({ json: TODAY }))
  await page.goto('/')

  const card = page.getByRole('region', { name: /^Today/ })
  await expect(card).toContainText('Next · Work')
  await expect(card).toContainText('Standup')
  await expect(card.getByRole('img', { name: '24 min' })).toBeVisible()
  await expect(card.getByRole('list', { name: 'All day' })).toContainText("Mama's birthday")
  await expect(card.getByRole('img', { name: 'The day from 07:00 to 23:00' })).toBeVisible()
})
