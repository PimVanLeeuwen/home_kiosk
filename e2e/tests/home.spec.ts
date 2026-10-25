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
  // The full pool unfolds the NAS card by itself; Services stays folded in its chip until opened.
  await expect(page.getByRole('region', { name: 'NAS' }).getByRole('meter', { name: 'volume2' })).toBeVisible()
  await expect(page.getByRole('region', { name: 'Services' })).toHaveCount(0)
  const chip = page.getByRole('button', { name: /^Services: 1 \/ 1 up/ })
  await chip.click()
  await expect(chip).toHaveAttribute('aria-expanded', 'true')
  await expect(page.getByRole('region', { name: 'Services' }).getByRole('link', { name: /Jellyfin/ })).toContainText('2 streaming')
  await page.keyboard.press('Escape')
  await expect(page.getByRole('region', { name: 'Services' })).toHaveCount(0)
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

const LAUNDRY_AT = (h: number, m: number) => new Date(2026, 9, 14, h, m).toISOString()
const LAUNDRY = {
  as_of: LAUNDRY_AT(10, 13), stale: false, showing: true,
  machines: [
    { id: 'w', name: 'Washing machine', kind: 'washer', state: 'running', online: true, program: 'Cotton',
      remaining_minutes: 38, total_minutes: 95, ready_at: LAUNDRY_AT(10, 52), done_at: null, door_open: false, error: null },
    { id: 'd', name: 'Tumble dryer', kind: 'dryer', state: 'done', online: true, program: 'Cotton',
      remaining_minutes: null, total_minutes: null, ready_at: null, done_at: LAUNDRY_AT(9, 41), door_open: false, error: null },
  ],
}

test('Home shows the laundry while a machine runs or is done', async ({ page }) => {
  await page.clock.install({ time: new Date(2026, 9, 14, 10, 14) })
  await page.route('**/api/laundry', (route) => route.fulfill({ json: LAUNDRY }))
  await page.goto('/')

  const card = page.getByRole('region', { name: 'Laundry' })
  await expect(card).toContainText('Ready at 10:52')
  await expect(card).toContainText('Take it out')

  await page.unroute('**/api/laundry')
  await page.route('**/api/laundry', (route) => route.fulfill({ json: { ...LAUNDRY, showing: false } }))
  await page.reload()
  await expect(page.getByRole('heading', { level: 1 })).toBeVisible()
  await expect(page.getByRole('region', { name: 'Laundry' })).toHaveCount(0)
})

test('Home shows the Apple devices with what plays per room', async ({ page }) => {
  const dev = (id: string, kind: string, thread: boolean | null, online = true) => ({ id, name: id, kind, online, offline_since: null, thread })
  await page.route('**/api/apple', (route) => route.fulfill({ json: {
    as_of: new Date().toISOString(), stale: false,
    rooms: [
      { id: 'living-room', name: 'Living room', devices: [dev('Woonkamer', 'homepod', true), dev('Apple TV Living Room', 'tv', true)],
        playing: { state: 'playing', media: 'music', title: 'Nightcall', subtitle: 'Kavinsky', app: 'Music', device: 'Woonkamer', artwork: false } },
      { id: 'bathroom', name: 'Bathroom', devices: [dev('Badkamer', 'homepod_mini', true, false)], playing: null },
    ],
  } }))
  await page.goto('/')

  const card = page.getByRole('region', { name: 'Apple devices' })
  await expect(card.getByText('1 offline')).toBeVisible()
  await expect(card.getByRole('img')).toHaveAccessibleName(/Bathroom: 1 device, Badkamer offline/)
  await expect(card.getByRole('list', { name: 'Playing' })).toContainText('Nightcall')
  await expect(card).toContainText('Thread · 2 of 3 border routers')
})

const AIR_AT = (h: number, m: number) => new Date(2026, 9, 21, h, m).toISOString()
const AIR = {
  as_of: AIR_AT(21, 4), stale: false, room: 'Living room', available: true,
  temperature: 23.6, humidity: 52, co2: 980, pm25: 6, quality: 'Good', level: 'stuffy', outside: 9,
  history: Array.from({ length: 97 }, (_, i) => ({ at: AIR_AT(13, 0), co2: Math.round(470 + 510 * (i / 96) ** 2) })),
}

test('Home shows the living room air with its CO2 word', async ({ page }) => {
  await page.clock.install({ time: new Date(2026, 9, 21, 21, 5) })
  await page.route('**/api/air', (route) => route.fulfill({ json: AIR }))
  await page.goto('/')

  const card = page.getByRole('region', { name: 'Air' })
  await expect(card).toContainText('23,6°')
  await expect(card).toContainText('Getting stuffy')
  await expect(card.getByRole('img', { name: 'CO₂ 980 ppm, getting stuffy' })).toBeVisible()
  await expect(card.getByRole('img', { name: 'CO₂ over the last 8 hours' })).toBeVisible()
})


const DNS = {
  as_of: new Date().toISOString(), stale: false, answering: true, failing: null, failing_since: null, protection: true,
  queries: 12480, blocked: 1530, share: 12.3,
  hours: Array.from({ length: 24 }, (_, i) => ({ queries: 500, blocked: 40 + i })),
  top_blocked: 'doubleclick.net', top_blocked_count: 312,
}

test('Home folds ad blocking into its chip, and unfolds it when AdGuard stops answering', async ({ page }) => {
  await page.route('**/api/dns', (route) => route.fulfill({ json: DNS }))
  await page.goto('/')

  const chip = page.getByRole('button', { name: /^Ads blocked: 12,3%/ })
  await expect(chip).toBeVisible()
  await expect(page.getByRole('region', { name: 'Ad blocking' })).toHaveCount(0)
  await chip.click()
  const card = page.getByRole('region', { name: 'Ad blocking' })
  await expect(card).toContainText('1.530')
  await expect(card).toContainText('doubleclick.net')
  await page.keyboard.press('Escape')

  await page.unroute('**/api/dns')
  await page.route('**/api/dns', (route) => route.fulfill({ json: { ...DNS, answering: false, stale: true } }))
  await page.reload()
  await expect(page.getByRole('button', { name: /^Ads blocked: Down/ })).toBeVisible()
  await expect(page.getByRole('region', { name: 'Ad blocking' })).toContainText('AdGuard is not answering')
})
