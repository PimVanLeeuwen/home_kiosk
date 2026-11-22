import { render, screen, within } from '@testing-library/react'
import type { ReactNode } from 'react'
import { MemoryRouter } from 'react-router'
import { BACKUPS, SERVICES, backupRun, nasFixture } from '../../test/fixtures'
import { stubApi } from '../../test/stubApi'
import type { BackupHistory, Nas, ServicesResponse } from '../../lib/types'
import { BackupCard } from './BackupCard'
import { NasCard } from './NasCard'
import { ServicesCard } from './ServicesCard'

/**
 * Today's house cards (NAS, Backups, Services) on their own: on Today they fold into the
 * healthy line while all is well and only show as a cell with a problem (plan.md M38).
 */
let api: Record<string, unknown> = {}
function setup(over: Record<string, unknown> = {}) {
  api = { '/api/nas': nasFixture(), '/api/services': SERVICES, ...over }
  stubApi(api)
}
const inRouter = (ui: ReactNode) => render(<MemoryRouter>{ui}</MemoryRouter>)

async function nasCard() {
  inRouter(<NasCard nas={api['/api/nas'] as Nas} error={undefined} />)
  return screen.findByRole('region', { name: 'NAS' })
}
async function backupCard() {
  inRouter(<BackupCard nas={api['/api/nas'] as Nas} error={undefined} history={api['/api/backups'] as BackupHistory | undefined} />)
  return screen.findByRole('region', { name: 'Backups' })
}
async function servicesCard() {
  inRouter(<ServicesCard services={(api['/api/services'] as ServicesResponse).groups.flatMap((g) => g.services)} error={undefined} />)
  return screen.findByRole('region', { name: 'Services' })
}

describe('house cards', () => {
  it('shows the fullest pool on a dial, load with 24-hour lines and a dot per disk', async () => {
    const point = (h: number, cpu: number, ram: number) => ({ t: new Date(2026, 9, 12, h).toISOString(), cpu, ram, temp: 44, rx_mbps: 1, tx_mbps: 1 })
    setup({
      '/api/nas/history': [point(8, 9, 23), point(9, 14, 24), point(10, 11, 24)],
      '/api/ups': { as_of: '', stale: false, name: 'ups0', model: null, status: 'online', status_raw: 'OL', charge: 100, charge_low: 20, load: 12, outages: [] },
    })

    const nas = await nasCard()
    // The fullest pool is the dial; the next one a thin bar.
    expect(await within(nas).findByRole('meter', { name: 'volume3' })).toHaveAttribute('aria-valuenow', '36')
    expect(within(nas).getByText('volume3 · 1,4 TB of 4,0 TB')).toBeInTheDocument()
    expect(within(nas).getByText('No growth trend yet')).toBeInTheDocument()
    expect(within(nas).getByRole('meter', { name: 'volume1' })).toBeInTheDocument()
    // The healthy line on Today says how the NAS is; the card repeats no state pill.
    expect(within(nas).queryByText('Healthy')).not.toBeInTheDocument()

    expect(within(nas).getByText('CPU · 44 °C')).toBeInTheDocument()
    expect(within(nas).getByText('11%')).toBeInTheDocument()
    expect(await within(nas).findByRole('img', { name: 'CPU, last 24 hours' })).toBeInTheDocument()
    expect(within(nas).getByRole('img', { name: 'Memory, last 24 hours' })).toBeInTheDocument()
    expect(within(nas).getByText('1 of 1')).toBeInTheDocument()
    expect(within(nas).getByRole('img', { name: 'sda: healthy' })).toBeInTheDocument()

    expect(within(nas).getByText(/Network ↓ 19,2 Mbit\/s/)).toBeInTheDocument()
    expect(await within(nas).findByText('UPS on mains · 100%')).toBeInTheDocument()
  })

  it('shows the last backup and service tiles with stats', async () => {
    setup()

    expect(await within(await backupCard()).findByText('Succeeded')).toBeInTheDocument()
    const services = await servicesCard()
    expect(await within(services).findByRole('link', { name: /Jellyfin/ })).toHaveTextContent('1 streaming')
  })

  it('shows a failed night with its seal, the failed volume and the nights before', async () => {
    setup({ '/api/backups': BACKUPS })

    const card = await backupCard()
    expect(await within(card).findByRole('img', { name: 'Backup failed' })).toBeInTheDocument()
    expect(within(card).getAllByText('Failed')).toHaveLength(2) // the pill and the result
    expect(within(card).getByText('volume3')).toBeInTheDocument()
    expect(within(card).getByText('Failed · 19 min')).toBeInTheDocument()
    expect(within(card).queryByText('volume1')).not.toBeInTheDocument() // fine volumes stay in the count
    expect(within(card).getByText('2 volumes · 23 min · 2,5 GB')).toBeInTheDocument()
    // The route stops moving after a failed night.
    expect(within(card).getByRole('img', { name: 'NAS to Hetzner · encrypted' }).querySelector('i')).toBeNull()
    const bars = within(card).getByRole('img', { name: 'Backup durations, last 3 nights' })
    expect(bars.querySelectorAll('rect')[2]).toHaveAttribute('fill', 'var(--color-down)')
    expect(within(card).getByText('last night: failed')).toBeInTheDocument()
    expect(within(card).getByText(/Next run due/)).toBeInTheDocument()
  })

  it('names last night\'s failure under the bars, not an older slow night', async () => {
    const run = (day: number, minutes: number, ok = true) => ({
      ...backupRun(day, ok), finished: new Date(new Date(backupRun(day).started).getTime() + minutes * 60_000).toISOString(),
    })
    setup({ '/api/backups': { ...BACKUPS, runs: [run(28, 20, false), run(27, 20), run(26, 45), run(25, 20)] } })

    const card = await backupCard()
    const label = await within(card).findByText('last night: failed')
    expect(label).toHaveAttribute('data-tone', 'down')
    expect(within(card).queryByText('slow')).not.toBeInTheDocument()
  })

  it('shows a good night as all safe, a slow night in grey and the restore check', async () => {
    const night = (daysAgo: number, minutes: number) => {
      const start = new Date()
      start.setDate(start.getDate() - daysAgo)
      start.setHours(Math.min(start.getHours(), 3), 0, 0, 0)
      if (daysAgo === 0 && start > new Date()) start.setTime(Date.now() - 3_600_000)
      return { ...backupRun(1), started: start.toISOString(), finished: new Date(start.getTime() + minutes * 60_000).toISOString() }
    }
    setup({
      '/api/backups': { ...BACKUPS, runs: [night(0, 20), night(1, 21), night(2, 40), night(3, 20)] },
      '/api/database-dumps': { as_of: '', stale: false, databases: [], runs: [], restore_checks: [], last_verified: new Date(Date.now() - 12 * 86_400_000).toISOString() },
    })

    const card = await backupCard()
    expect(await within(card).findByText('All safe')).toBeInTheDocument()
    expect(within(card).getByRole('img', { name: 'Backup succeeded' })).toBeInTheDocument()
    expect(await within(card).findByText('Restore verified 12 days ago')).toHaveClass('text-up')
    expect(within(card).getByRole('img', { name: 'NAS to Hetzner · encrypted' }).querySelector('i')).not.toBeNull()
    const rects = within(card).getByRole('img', { name: 'Backup durations, last 4 nights' }).querySelectorAll('rect')
    expect(rects[1]).toHaveAttribute('fill', 'var(--color-faint)') // 40 min against a usual 20: slow, not a problem
    expect(within(card).getByText('slow')).toBeInTheDocument()
  })

  it('warns when the newest restore check failed', async () => {
    setup({
      '/api/backups': BACKUPS,
      '/api/database-dumps': {
        as_of: '', stale: false, databases: [], runs: [], last_verified: '2026-09-01T05:20:00Z',
        restore_checks: [{ started: new Date(Date.now() - 2 * 86_400_000).toISOString(), finished: new Date(Date.now() - 2 * 86_400_000).toISOString(), ok: false, checks: [] }],
      },
    })

    const card = await backupCard()
    expect(await within(card).findByText('Last restore check failed 2 days ago')).toHaveClass('text-down')
  })
})
