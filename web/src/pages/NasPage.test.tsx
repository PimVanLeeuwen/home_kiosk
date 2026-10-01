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
})
