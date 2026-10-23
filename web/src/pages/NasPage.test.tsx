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

  it('draws each instrument edge to edge with its peak, upload under download', async () => {
    setup()

    const cpu = await screen.findByRole('region', { name: 'CPU' })
    expect(within(cpu).getByRole('img', { name: 'CPU, last 24 hours' }).querySelector('[data-testid="peak"]')).not.toBeNull()
    // A 35% peak tops a scale of 42%, so the day's shape reads instead of a flat line.
    const cpuLine = within(cpu).getByRole('img', { name: 'CPU, last 24 hours' }).querySelector('polyline')!
    expect(cpuLine.getAttribute('points')).toContain('300.0,27.7')
    const network = screen.getByRole('region', { name: 'Network' })
    expect(within(network).getByText('↓ 19,2')).toBeInTheDocument()
    const chart = within(network).getByRole('img', { name: 'Network download and upload, last 24 hours' })
    expect(chart.querySelector('[data-testid="secondary"]')).not.toBeNull()
  })

  it('draws a cool temperature in blue, and turns amber from 70 °C and red from 80 °C', async () => {
    const line = () =>
      within(screen.getByRole('region', { name: 'CPU temperature' }))
        .getByRole('img', { name: 'CPU temperature, last 24 hours' })
        .querySelector('polyline')!
    stubApi({ '/api/nas': nasFixture({ cpu_temp_c: 48 }), '/api/nas/history': [point(0), point(10)] })
    const { unmount } = renderRoute('/nas')
    expect(await screen.findByText('48 °C')).not.toHaveClass('text-warn')
    expect(line()).toHaveAttribute('stroke', 'var(--color-data-blue)')
    unmount()

    stubApi({ '/api/nas': nasFixture({ cpu_temp_c: 74 }), '/api/nas/history': [point(0), point(10)] })
    const second = renderRoute('/nas')
    expect(await screen.findByText('74 °C')).toHaveClass('text-warn')
    expect(line()).toHaveAttribute('stroke', 'var(--color-warn)')
    second.unmount()

    stubApi({ '/api/nas': nasFixture({ cpu_temp_c: 83 }), '/api/nas/history': [point(0), point(10)] })
    renderRoute('/nas')
    expect(await screen.findByText('83 °C')).toHaveClass('text-down')
  })

  it('lists pools with free space and how long until they are full', async () => {
    setup()

    const storage = await screen.findByRole('region', { name: 'Storage' })
    expect(within(storage).getByRole('meter', { name: 'volume2' })).toHaveAttribute('aria-valuenow', '92')
    expect(within(storage).getByText('No growth trend yet')).toBeInTheDocument()
    expect(within(storage).getByText('Full in about 3 years')).toBeInTheDocument()
    expect(within(storage).getByText('Full in about 7 months')).toBeInTheDocument()
    expect(within(storage).getByText('5,2 TB of 6,0 TB')).toBeInTheDocument()
    expect(within(storage).getByText('800 GB free')).toBeInTheDocument()
    // Every pool is a dial; the runway turns amber when it is short.
    expect(within(storage).getByRole('meter', { name: 'volume1' })).toHaveAttribute('aria-valuenow', '17')
    expect(within(storage).getByText('Full in about 7 months')).not.toHaveClass('text-warn')
    // All pools together: 6,28 of 10,48 TB.
    expect(within(storage).getByRole('meter', { name: 'All pools' })).toHaveAttribute('aria-valuenow', '60')
    expect(within(storage).getByText('6,3 TB of 10,5 TB used')).toBeInTheDocument()
  })

  it('says the NAS needs a look in the header when a pool is full or a disk has trouble', async () => {
    setup()
    expect(await screen.findByText('Needs a look')).toBeInTheDocument()
  })

  it('shows disk temperatures and SMART health', async () => {
    setup()

    const disks = await screen.findByRole('region', { name: 'Disks' })
    const bays = within(within(disks).getByRole('list', { name: /SMART health/ })).getAllByRole('listitem')
    expect(bays.map((r) => r.textContent)).toEqual(['sda42 °CHealthy', 'sdb51 °CWarnings', 'sdc–Failing'])
    // A warm disk reads amber; a disk in trouble pulses; the header counts the worst.
    expect(within(bays[1]).getByText('51 °C')).toHaveClass('text-warn')
    expect(bays[0].querySelector('.motion-safe\\:animate-halo')).toBeNull()
    expect(bays[2].querySelector('.motion-safe\\:animate-halo')).not.toBeNull()
    expect(within(disks).getByText('2 failing')).toBeInTheDocument()
    // The temperature bar fills from 25 °C to 60 °C: 42 °C is about half.
    expect((bays[0].querySelector('.absolute') as HTMLElement).style.width).toMatch(/^48\.57/)
    expect(within(disks).getByText(/Containers: 37 of 37 running/)).toBeInTheDocument()
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
    // A cut that stopped the services has a red dot on the timeline.
    expect(cuts[1].querySelector('.bg-down')).not.toBeNull()
    expect(cuts[0].querySelector('.bg-down')).toBeNull()
    expect(within(card).getByRole('meter', { name: 'Battery' })).toHaveAttribute('data-tone', 'up')
    expect(within(card).getByText('Stops at').nextElementSibling).toHaveTextContent('15%')
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
    // The ring and the pill turn amber while on battery.
    expect(within(card).getByRole('meter', { name: 'Battery' })).toHaveAttribute('data-tone', 'warn')
    expect(within(card).getByRole('meter', { name: 'Battery' })).toHaveTextContent('71%')
    expect(within(card).getAllByText('On battery')).toHaveLength(2)
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
    expect(hosts[0]).toHaveTextContent('Tunnelhttp://192.168.1.10:5984· answers 200')
    expect(hosts[1]).toHaveTextContent('Not allowed')
    expect(hosts[1]).toHaveTextContent('no answer')
    expect(within(card).getByText(/1 hostname not on the allowlist/)).toHaveClass('text-down')
    expect(within(card).getByRole('img', { name: 'Something unexpected is public' })).toBeInTheDocument()
    expect(hosts[1].querySelector('.motion-safe\\:animate-halo')).not.toBeNull()
    // The home IP is not shown.
    expect(card).not.toHaveTextContent('203.0.113.7')
  })

  it('shows a green shield when everything public is allowed', async () => {
    stubApi({ '/api/nas': NAS, '/api/exposure': { ...EXPOSURE, hosts: [EXPOSURE.hosts[0]] } })
    renderRoute('/nas')

    const card = await screen.findByRole('region', { name: 'Exposure' })
    expect(within(card).getByRole('img', { name: 'Nothing unexpected is public' })).toBeInTheDocument()
    expect(within(card).getByText('Nothing public beyond the allowlist')).not.toHaveClass('text-down')
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
    expect(within(card).queryByRole('img', { name: /is public/ })).not.toBeInTheDocument()
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
    expect(card.querySelector('.motion-safe\\:animate-halo')).not.toBeNull()
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
