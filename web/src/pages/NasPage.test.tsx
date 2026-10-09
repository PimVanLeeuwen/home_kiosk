import { screen, within } from '@testing-library/react'
import type { NasPoint } from '../lib/types'
import { nasFixture } from '../test/fixtures'
import { renderRoute } from '../test/renderRoute'
import { stubApi } from '../test/stubApi'

const point = (minute: number, over: Partial<NasPoint> = {}): NasPoint => ({
  t: new Date(Date.UTC(2026, 9, 1, 12, minute)).toISOString(),
  cpu: 10, ram: 70, temp: 55, rx_mbps: 2, tx_mbps: 1, ...over,
})

const NAS = nasFixture({
  uptime_seconds: 86 * 86_400 + 500,
  mem_total_bytes: 7_500_000_000,
  ram_pct: 77.2,
  cpu_temp_c: 62,
  storage: {
    used_pct: 60,
    pools: [
      { name: 'volume2', used_bytes: 5.2e12, total_bytes: 6e12, used_pct: 92.4, free_bytes: 0.8e12, projection_months: null },
      { name: 'volume1', used_bytes: 8e10, total_bytes: 4.8e11, used_pct: 16.8, free_bytes: 4e11, projection_months: 39.9 },
      { name: 'volume3', used_bytes: 1e12, total_bytes: 4e12, used_pct: 25, free_bytes: 3e12, projection_months: 7.4 },
    ],
  },
  disks: [
    { name: 'sda', temp_c: 42, smart: 'ok' },
    { name: 'sdb', temp_c: 51, smart: 'warn' },
    { name: 'sdc', temp_c: null, smart: 'fail' },
  ],
})

function setup(history: NasPoint[] = [point(0, { cpu: 8 }), point(10, { cpu: 35, temp: 66 }), point(20)]) {
  stubApi({ '/api/nas': NAS, '/api/nas/history': history })
  renderRoute('/nas')
}

describe('NasPage', () => {
  it('shows the host, uptime and current figures with 24-hour peaks', async () => {
    setup()

    expect(await screen.findByText('dev-minotaur · up 86 days')).toBeInTheDocument()
    const cpu = screen.getByRole('region', { name: 'CPU' })
    expect(await within(cpu).findByText('Peak 35% in 24 hours')).toBeInTheDocument()
    expect(within(cpu).getByRole('img', { name: 'CPU, last 24 hours' })).toBeInTheDocument()
    expect(within(screen.getByRole('region', { name: 'Memory' })).getByText('5,8 GB of 7,5 GB')).toBeInTheDocument()
    expect(within(screen.getByRole('region', { name: 'CPU temperature' })).getByText('Peak 66 °C in 24 hours')).toBeInTheDocument()
  })

  it('lists pools with free space and how long until they are full', async () => {
    setup()

    const storage = await screen.findByRole('region', { name: 'Storage' })
    expect(within(storage).getByRole('meter', { name: 'volume2' })).toHaveAttribute('aria-valuenow', '92')
    expect(within(storage).getByText('No growth trend yet')).toBeInTheDocument()
    expect(within(storage).getByText('Full in about 3 years')).toBeInTheDocument()
    expect(within(storage).getByText('Full in about 7 months')).toBeInTheDocument()
    expect(within(storage).getByText(/92,4% used · 800 GB free/)).toBeInTheDocument()
  })

  it('shows disk temperatures and SMART health', async () => {
    setup()

    const disks = await screen.findByRole('region', { name: 'Disks' })
    const rows = within(disks).getAllByRole('row').slice(1)
    expect(rows.map((r) => r.textContent)).toEqual(['sda42 °CHealthy', 'sdb51 °CWarnings', 'sdc–Failing'])
    expect(within(disks).getByRole('link', { name: 'Open Docker' })).toHaveAttribute('href', '/docker')
  })

  it('explains an empty history', async () => {
    setup([])

    expect((await screen.findAllByText(/fills in as readings come in/)).length).toBe(4)
  })

  it('says when NAS data is not available', async () => {
    stubApi({})
    renderRoute('/nas')

    expect(await screen.findByText('NAS data is not available right now.')).toBeInTheDocument()
  })
  // Local time, so the expected text holds in any time zone (CI runs in UTC).
  const local = (day: number, hour: number, minute: number) => new Date(2026, 9, day, hour, minute).toISOString()
  const UPS = {
    as_of: '2026-10-09T08:00:00Z', stale: false, name: 'ups0', model: 'UGREEN US3000', status: 'online',
    status_raw: 'OL', charge: 100, charge_low: 15, load: 1,
    outages: [
      { started_at: local(6, 10, 2), ended_at: local(6, 10, 41), lowest_charge: 62, reached_low: false },
      { started_at: local(4, 18, 0), ended_at: local(4, 20, 5), lowest_charge: 14, reached_low: true },
    ],
  }

  it('shows the UPS with its battery and the last power cuts', async () => {
    stubApi({ '/api/nas': NAS, '/api/ups': UPS })
    renderRoute('/nas')

    const card = await screen.findByRole('region', { name: 'UPS' })
    expect(within(card).getByText('Status').nextElementSibling).toHaveTextContent('On mains')
    expect(within(card).getByText('Load').nextElementSibling).toHaveTextContent('1%')
    expect(within(card).getByRole('meter', { name: 'Battery' })).toHaveAttribute('aria-valuenow', '100')
    const cuts = within(card).getAllByRole('listitem')
    expect(cuts[0]).toHaveTextContent('Tue 6 Oct 10:02, 39 min, down to 62%')
    expect(cuts[1]).toHaveTextContent('2 h 5 min, down to 14% (services stopped)')
  })

  it('says since when the UPS is on battery', async () => {
    stubApi({
      '/api/nas': NAS,
      '/api/ups': {
        ...UPS, status: 'on_battery', status_raw: 'OB DISCHRG', charge: 71,
        outages: [{ started_at: new Date().toISOString(), ended_at: null, lowest_charge: 71, reached_low: false }],
      },
    })
    renderRoute('/nas')

    const card = await screen.findByRole('region', { name: 'UPS' })
    expect(within(card).getByText('Status').nextElementSibling).toHaveTextContent(/On battery since today/)
    expect(within(card).getByText('None recorded.')).toBeInTheDocument()
    expect(within(card).getByRole('meter', { name: 'Battery' }).firstElementChild).toHaveClass('bg-warn')
  })

  it('leaves the UPS out when the hub has no UPS data', async () => {
    stubApi({ '/api/nas': NAS })
    renderRoute('/nas')
    await screen.findByRole('region', { name: 'Disks' })
    expect(screen.queryByRole('region', { name: 'UPS' })).not.toBeInTheDocument()
  })
  const EXPOSURE = {
    as_of: '2026-10-09T08:00:00Z', stale: false, zone: 'example.com', home_ip: '203.0.113.7', error: null,
    hosts: [
      { hostname: 'couchdb.example.com', source: 'tunnel', target: 'http://192.168.1.10:5984', allowed: true, status: 200, error: null },
      { hostname: 'immich.example.com', source: 'tunnel', target: 'http://192.168.1.10:2283', allowed: false, status: null, error: 'no answer' },
    ],
  }

  it('lists the public hostnames and flags one that is not allowed', async () => {
    stubApi({ '/api/nas': NAS, '/api/exposure': EXPOSURE })
    renderRoute('/nas')

    const card = await screen.findByRole('region', { name: 'Exposure' })
    const hosts = within(card).getAllByRole('listitem')
    expect(hosts[0]).toHaveTextContent('couchdb.example.comAllowed')
    expect(hosts[0]).toHaveTextContent('Tunnel to http://192.168.1.10:5984 · answers 200')
    expect(hosts[1]).toHaveTextContent('Not allowed')
    expect(hosts[1]).toHaveTextContent('no answer')
    expect(within(card).getByText(/1 hostname not on the allowlist/)).toHaveClass('text-down')
    // The home IP is not shown.
    expect(card).not.toHaveTextContent('203.0.113.7')
  })

  it('says why the audit could not run', async () => {
    stubApi({
      '/api/nas': NAS,
      '/api/exposure': { ...EXPOSURE, hosts: [], error: 'No Cloudflare API token set (CLOUDFLARE_API_TOKEN)' },
    })
    renderRoute('/nas')

    const card = await screen.findByRole('region', { name: 'Exposure' })
    expect(within(card).getByRole('status')).toHaveTextContent('No Cloudflare API token set')
    expect(within(card).queryByText(/Nothing public beyond the allowlist/)).not.toBeInTheDocument()
  })
  const scanRun = (open: number[], error: string | null = null) => ({
    started: '2026-10-09T03:30:00Z', finished: '2026-10-09T03:36:00Z', ports_checked: error ? 0 : 65535, open, error,
  })

  it('shows the port scan from outside with any open ports', async () => {
    stubApi({
      '/api/nas': NAS, '/api/exposure': EXPOSURE,
      '/api/exposure/scan': { as_of: '2026-10-09T03:36:00Z', stale: false, runs: [scanRun([22, 32400])] },
    })
    renderRoute('/nas')

    const card = await screen.findByRole('region', { name: 'Exposure' })
    expect(within(card).getByText(/Open on the home IP: 22, 32400\./)).toHaveClass('text-down')
  })

  it('says the scan found nothing, or why it failed, or that none came in', async () => {
    stubApi({
      '/api/nas': NAS, '/api/exposure': EXPOSURE,
      '/api/exposure/scan': { as_of: '2026-10-09T03:36:00Z', stale: false, runs: [scanRun([])] },
    })
    const { unmount } = renderRoute('/nas')
    expect(await screen.findByText(/No open ports \(all 65\.535 checked\)/)).toBeInTheDocument()
    unmount()

    stubApi({
      '/api/nas': NAS, '/api/exposure': EXPOSURE,
      '/api/exposure/scan': { as_of: '2026-10-09T03:36:00Z', stale: false, runs: [scanRun([], 'Could not get the home IP from the hub')] },
    })
    const second = renderRoute('/nas')
    expect(await screen.findByText(/failed: Could not get the home IP from the hub/)).toHaveClass('text-warn')
    second.unmount()

    stubApi({ '/api/nas': NAS, '/api/exposure': EXPOSURE })
    renderRoute('/nas')
    expect(await screen.findByText(/No scan received yet/)).toBeInTheDocument()
  })
})
