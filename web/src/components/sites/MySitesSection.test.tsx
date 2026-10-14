import { render, screen, within } from '@testing-library/react'
import type { Site } from '../../lib/types'
import { stubApi } from '../../test/stubApi'
import { MySitesSection } from './MySitesSection'

const NOW = new Date(2026, 9, 14, 11, 30)
const month = (marks: Record<number, Site['days'][number]> = {}) => Array.from({ length: 30 }, (_, d) => marks[d] ?? 'up')
const site = (id: number, name: string, group: string, over: Partial<Site> = {}): Site => ({
  id, name, group, up: true, down_since: null, ping_ms: 120, uptime_pct: 100, days: month(), ...over,
})
const SITES = [
  site(13, 'AOC', 'Personal'),
  site(21, 'Hubble Website', 'Hubble', { days: month({ 17: 'blip' }), uptime_pct: 99.97 }),
  site(43, 'Meteor Website', 'Hubble', { up: false, down_since: new Date(2026, 9, 14, 11, 18).toISOString(), uptime_pct: 99.92 }),
]

function show(sites: Site[] | null, stale = false) {
  vi.useFakeTimers({ toFake: ['Date'] })
  vi.setSystemTime(NOW)
  stubApi(sites ? { '/api/sites': { as_of: NOW.toISOString(), stale, sites } } : {})
  render(<MySitesSection />)
}

afterEach(() => vi.useRealTimers())

describe('MySitesSection', () => {
  it('draws a ring per site with its days, and the sites up in the middle', async () => {
    show(SITES)

    const rings = await screen.findByRole('img', { name: '2 of 3 sites up' })
    expect(rings.querySelectorAll('[data-site]')).toHaveLength(3)
    const hubble = rings.querySelector('[data-site="Hubble Website"]')!
    expect(hubble.querySelectorAll('[data-day="blip"]')).toHaveLength(1)
    // A site down now pulses today's segment.
    const meteor = rings.querySelector('[data-site="Meteor Website"]')!
    expect(meteor.querySelectorAll('path')[29]).toHaveAttribute('data-day', 'down')
  })

  it("lists the sites in Kuma's groups, with uptime below 100% and a site that is down", async () => {
    show(SITES)

    expect(await screen.findByText('1 down')).toBeInTheDocument()
    const hubble = screen.getByRole('region', { name: 'Hubble' })
    expect(within(hubble).getByText('99,97%')).toHaveClass('text-warn')
    expect(within(hubble).getByText('down for 12 min')).toHaveClass('text-down')
    const personal = screen.getByRole('region', { name: 'Personal' })
    expect(within(personal).getByText('AOC')).toBeInTheDocument()
    expect(within(personal).queryByText(/%/)).toBeNull()
  })

  it('says all up, and when the figures are the last known ones', async () => {
    show([SITES[0]], true)

    expect(await screen.findByText('All up')).toBeInTheDocument()
    expect(screen.getByText('Showing the last known figures.')).toBeInTheDocument()
  })

  it('says when there are no sites or no answer', async () => {
    show([])
    expect(await screen.findByText("No sites on Kuma's status page yet.")).toBeInTheDocument()
  })

  it('says so when My sites is not available', async () => {
    show(null)
    expect(await screen.findByText('My sites is not available right now.')).toBeInTheDocument()
  })
})
