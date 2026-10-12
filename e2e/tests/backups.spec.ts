import { expect, test } from '@playwright/test'

const vol = (name: string, ok = true) => ({
  name, ok, exit_code: ok ? 0 : 7, seconds: name === 'volume1' ? 241 : 1140, bytes: ok ? 500_000_000 : 10,
  transfers: 12, checks: 5120, deletes: 0, errors: ok ? 0 : 1, last_error: ok ? null : 'quota exceeded',
})
const run = (day: number, ok = true) => ({
  started: `2026-09-${day}T01:00:00Z`, finished: `2026-09-${day}T01:23:00Z`, ok,
  volumes: [vol('volume1'), vol('volume3', ok)],
})
const HISTORY = {
  as_of: new Date().toISOString(), stale: false,
  runs: [run(28, false), run(27), run(26)],
  volumes: [
    { name: 'volume1', last_run: run(28, false), last_success: '2026-09-28T01:23:00Z' },
    { name: 'volume3', last_run: run(28, false), last_success: '2026-09-27T01:23:00Z' },
  ],
  next_due: '2026-09-29T01:23:00Z',
  storage_box: {
    total: 1_099_511_627_776, used: 235_264_802_816, free: 864_246_824_960, used_pct: 21.4,
    at: '2026-09-28T01:23:00Z', projection_months: 31,
  },
}

test('Backups shows per-volume results and the run history', async ({ page }) => {
  await page.route('**/api/backups', (route) => route.fulfill({ json: HISTORY }))
  await page.goto('/backups')

  await expect(page.getByRole('region', { name: 'volume3' })).toContainText('quota exceeded')
  await expect(page.getByRole('region', { name: 'Last night' }).getByRole('img', { name: 'Backup durations, last 3 nights' })).toBeVisible()
  await expect(page.getByRole('region', { name: 'Last 3 runs' }).getByRole('row')).toHaveCount(4)
  const box = page.getByRole('region', { name: 'Storage box' })
  await expect(box).toContainText('235 GB of 1,1 TB')
  await expect(box.getByRole('meter', { name: 'Hetzner' })).toBeVisible()
  await expect(box).toContainText('Full in about 3 years')
})

const MIRROR = {
  as_of: new Date().toISOString(), stale: false, enabled: true, dir: '/backups/github', error: null,
  owners: [
    { login: 'PimVanLeeuwen', label: 'Mine', removed: [], error: null, repos: [
      { full_name: 'PimVanLeeuwen/home_kiosk', archived: false, ok: true, error: null, mirrored_at: '2026-10-04T00:01:00Z', bytes: 4_200_000 },
    ] },
    { login: 'Hubble-Community-Cafe', label: 'Hubble', removed: [], error: null, repos: [
      { full_name: 'Hubble-Community-Cafe/web', archived: false, ok: false, error: 'fatal: repository not found', mirrored_at: null, bytes: null },
    ] },
  ],
  runs: [{ started: '2026-10-04T00:00:00Z', finished: '2026-10-04T00:02:00Z', ok: false, repos: 2, failed: 1, removed: 0, bytes: 4_200_000 }],
  last_success: null,
  next_due: '2026-10-05T00:00:00Z',
}

test('Backups shows the GitHub mirror and what failed', async ({ page }) => {
  await page.route('**/api/backups', (route) => route.fulfill({ json: HISTORY }))
  await page.route('**/api/github-mirror', (route) => route.fulfill({ json: MIRROR }))
  await page.goto('/backups')

  const card = page.getByRole('region', { name: 'GitHub mirror' })
  await expect(card).toContainText('Mine 1 · Hubble 1 · 1 failed')
  await expect(card).toContainText('Hubble-Community-Cafe/web: fatal: repository not found')
  await card.getByRole('link', { name: /Repos/ }).click()
  await expect(page).toHaveURL(/\/repos$/)
})

const DUMPS = {
  as_of: new Date().toISOString(), stale: false,
  databases: [
    { name: 'ghostfolio', label: 'Ghostfolio', kind: 'pg_dump', ok: true, at: '2026-10-09T00:30:05Z', bytes: 623_926, error: null, last_success: '2026-10-09T00:30:05Z' },
    { name: 'tandoor', label: 'Tandoor', kind: 'pg_dump', ok: false, at: '2026-10-09T00:30:05Z', bytes: null, error: 'pg_dump: error: connection refused', last_success: '2026-10-08T00:30:04Z' },
    { name: 'tracearr', label: 'Tracearr', kind: 'pg_dump', ok: true, at: '2026-10-09T00:30:05Z', bytes: 4_371_803, error: null, last_success: '2026-10-09T00:30:05Z' },
    { name: 'hub', label: 'Home hub', kind: 'sqlite', ok: true, at: '2026-10-09T00:45:01Z', bytes: 2_100_000, error: null, last_success: '2026-10-09T00:45:01Z' },
  ],
  runs: [
    { started: '2026-10-09T00:30:00Z', finished: '2026-10-09T00:30:05Z', ok: false, failed: 1 },
    { started: '2026-10-08T00:30:00Z', finished: '2026-10-08T00:30:04Z', ok: true, failed: 0 },
  ],
  last_verified: '2026-10-01T03:01:30Z',
  restore_checks: [{
    started: '2026-10-01T03:00:00Z', finished: '2026-10-01T03:01:30Z', ok: true,
    checks: [
      { name: 'download:databases', ok: true, detail: '3 files, identical to the local copies' },
      { name: 'ghostfolio', ok: true, detail: 'restored: 31 tables, 212 activities' },
    ],
  }],
}

test('Backups shows the database dumps and a failed one', async ({ page }) => {
  await page.route('**/api/backups', (route) => route.fulfill({ json: HISTORY }))
  await page.route('**/api/database-dumps', (route) => route.fulfill({ json: DUMPS }))
  await page.goto('/backups')

  const card = page.getByRole('region', { name: 'Database dumps' })
  await expect(card.getByRole('listitem')).toHaveCount(4)
  await expect(card).toContainText('pg_dump: error: connection refused')
  await expect(card).toContainText('Host job: 1 of 2 recent runs succeeded')
  const restore = page.getByRole('region', { name: 'Restore check' })
  await expect(restore).toContainText('Passed')
  await expect(restore).toContainText('restored: 31 tables, 212 activities')
})
