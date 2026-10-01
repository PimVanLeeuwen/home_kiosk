import type { BackupHistory, BackupRun, Nas, NewsResponse, Portfolio, ServicesResponse } from '../lib/types'

/** Shared API fixtures for page tests. Times are relative to now so "today" holds. */
export function nasFixture(over: Partial<Nas> = {}): Nas {
  const backupAt = new Date()
  backupAt.setHours(Math.min(backupAt.getHours(), 3), 31, 0, 0)
  return {
    as_of: new Date().toISOString(),
    stale: false,
    host: 'dev-minotaur',
    storage: {
      used_pct: 60.9,
      pools: [
        { name: 'volume3', used_bytes: 1.42e12, total_bytes: 3.98e12, used_pct: 35.7, free_bytes: 2.56e12 },
        { name: 'volume1', used_bytes: 7.7e10, total_bytes: 4.8e11, used_pct: 15.9, free_bytes: 4e11 },
      ],
    },
    cpu_pct: 11.2,
    ram_pct: 24.1,
    cpu_temp_c: 44,
    containers: { running: 37, total: 37 },
    disks: [{ name: 'sda', temp_c: 35, smart: 'ok' }],
    network: { rx_mbps: 19.2, tx_mbps: 2.4 },
    backup: { status: 'ok', at: backupAt.toISOString() },
    ...over,
  }
}

export const PORTFOLIO: Portfolio = {
  as_of: '2026-09-30T18:00:00Z',
  stale: false,
  currency: 'EUR',
  total_value: 24490.42,
  change: { day_abs: 220.1, day_pct: 0.91, month_pct: 2.44, year_pct: 11.8, all_pct: 38.2 },
  history: [
    { d: '2026-09-28', v: 24000 },
    { d: '2026-09-29', v: 24270 },
    { d: '2026-09-30', v: 24490 },
  ],
  holdings: [
    { symbol: 'VWRL', name: 'Vanguard FTSE All-World', value: 41220, day_pct: 0.6, weight_pct: 29 },
    { symbol: 'ASML', name: 'ASML Holding', value: 8905, day_pct: 4.2, weight_pct: 6 },
    { symbol: 'NVDA', name: 'NVIDIA', value: 6410, day_pct: -1.1, weight_pct: 4 },
    { symbol: 'AAPL', name: 'Apple', value: 5000, day_pct: 0.1, weight_pct: 3 },
  ],
}

export const NEWS: NewsResponse = {
  as_of: '2026-09-30T18:00:00Z',
  stale: false,
  groups: [
    {
      id: 'nl',
      title: 'Nederland',
      items: [
        { title: 'Kabinet presenteert Miljoenennota', source: 'NOS', published: '2026-09-30T17:48:00Z', age_label: '12 min ago', url: 'https://nos.nl/1' },
      ],
    },
    {
      id: 'tech',
      title: 'Tech',
      items: [
        { title: 'Old story', source: 'Ars', published: '2026-09-29T08:00:00Z', age_label: '1 day ago', url: 'https://ars/1' },
        { title: 'Jellyfin 12.1 lands', source: 'Hacker News', published: '2026-09-30T17:00:00Z', age_label: '1 hr ago', url: 'https://hn/1' },
      ],
    },
  ],
}

export const SERVICES: ServicesResponse = {
  as_of: '2026-09-30T18:00:00Z',
  stale: false,
  groups: [
    {
      name: 'Media',
      services: [
        { id: 'jellyfin', name: 'Jellyfin', group: 'Media', description: 'Media server', port: 8096, path: '/', container: 'jellyfin', widget: 'jellyfin', status: 'up', stats: [{ label: 'Streaming', value: 1, unit: 'count' }], stats_error: null },
      ],
    },
    {
      name: 'Arr',
      services: [
        { id: 'sonarr', name: 'Sonarr', group: 'Arr', description: 'TV', port: 8989, path: '/', container: 'sonarr', widget: null, status: 'up' },
      ],
    },
  ],
}

const vol = (name: string, ok = true, over: Partial<BackupRun['volumes'][number]> = {}) => ({
  name, ok, exit_code: ok ? 0 : 7, seconds: name === 'volume1' ? 241 : 1140,
  bytes: ok ? (name === 'volume1' ? 2_468_000_000 : 500_000_000) : 10, transfers: ok ? 118 : 0,
  checks: 5120, deletes: 3, errors: ok ? 0 : 1, last_error: ok ? null : 'quota exceeded', ...over,
})

export function backupRun(day: number, ok = true): BackupRun {
  return {
    started: `2026-09-${String(day).padStart(2, '0')}T01:00:00Z`,
    finished: `2026-09-${String(day).padStart(2, '0')}T01:23:00Z`,
    ok,
    volumes: [vol('volume1'), vol('volume3', ok)],
  }
}

/** Newest first: the 28th failed on volume3, the 27th and 26th succeeded. */
export const BACKUPS: BackupHistory = {
  as_of: '2026-09-28T12:00:00Z',
  stale: false,
  runs: [backupRun(28, false), backupRun(27), backupRun(26)],
  volumes: [
    { name: 'volume1', last_run: backupRun(28, false), last_success: '2026-09-28T01:23:00Z' },
    { name: 'volume3', last_run: backupRun(28, false), last_success: '2026-09-27T01:23:00Z' },
  ],
  next_due: '2026-09-29T01:23:00Z',
}
