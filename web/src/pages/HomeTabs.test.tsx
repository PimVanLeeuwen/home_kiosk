import { screen, within } from '@testing-library/react'
import type { Air, AppleDevices, Laundry, Machine } from '../lib/types'
import { outsideServices, ACTIONS_DELAYED } from '../test/outsideFixtures'
import { SERVICES } from '../test/fixtures'
import { renderRoute } from '../test/renderRoute'
import { stubApi } from '../test/stubApi'

const now = new Date().toISOString()
const AIR: Air = {
  as_of: now, stale: false, room: 'Living room', available: true,
  temperature: 22.9, humidity: 47, co2: 950, pm25: 2, quality: 'Good', level: 'stuffy', outside: 10,
  history: Array.from({ length: 24 }, (_, i) => ({ at: now, co2: 600 + i * 15 })),
}
const base = { online: true, door_open: false, error: null, done_at: null, program: null, remaining_minutes: null, total_minutes: null, ready_at: null }
const machine = (id: string, name: string, kind: Machine['kind'], over: Partial<Machine> = {}): Machine => ({ id, name, kind, state: 'idle', ...base, ...over })
const dev = (id: string, kind: 'tv' | 'homepod' | 'homepod_mini', thread: boolean | null, over = {}) => ({
  id, name: id, kind, online: true, offline_since: null, thread, ...over,
})
const APPLE: AppleDevices = {
  as_of: now, stale: false,
  rooms: [
    { id: 'living', name: 'Living room', devices: [dev('Living TV', 'tv', true), dev('Living pod', 'homepod', null)], playing: null },
    { id: 'bed', name: 'Bedroom', devices: [dev('Bedroom mini', 'homepod_mini', true, { online: false, offline_since: new Date(Date.now() - 2 * 3600e3).toISOString() })], playing: null },
  ],
}

describe('the pages built from Today cards (M38, 5f)', () => {
  it('Air shows the four readings as cells, then CO₂ as the ring and its 8 hours', async () => {
    stubApi({ '/api/air': AIR })
    renderRoute('/home/air')

    const readings = await screen.findByRole('region', { name: 'Readings' })
    expect(within(readings).getByRole('region', { name: 'Temperature' })).toHaveAttribute('data-cell', 'true')
    expect(within(readings).getByRole('region', { name: 'Temperature' })).toHaveTextContent('22,9°10° outside')
    expect(within(readings).getByRole('region', { name: 'CO₂' })).toHaveTextContent('950 ppmGetting stuffy')
    expect(within(readings).getByRole('region', { name: 'Fine dust' })).toHaveTextContent('Sensor says: Good')
    const co2 = screen.getByRole('region', { name: 'CO₂, the last 8 hours' })
    expect(within(co2).getByRole('img', { name: 'CO₂ 950 ppm, getting stuffy' })).toBeInTheDocument()
    expect(within(co2).getByRole('img', { name: 'CO₂ over the last 8 hours' })).toHaveClass('h-40')
    expect(document.title).toBe('Air · Home hub')
  })

  it('Laundry shows both machines while they are off, and what ConnectLife says about each', async () => {
    stubApi({
      '/api/laundry': {
        as_of: now, stale: false, showing: false,
        machines: [machine('w', 'Washing machine', 'washer'), machine('d', 'Tumble dryer', 'dryer', { door_open: true, online: false })],
      } satisfies Laundry,
    })
    renderRoute('/home/laundry')

    const machines = await screen.findByRole('region', { name: 'Machines' })
    expect(within(machines).getAllByText('Off')).toHaveLength(2)
    // Nothing runs: no pill, and no link to the page it is on.
    expect(within(machines).queryByText(/running/i)).toBeNull()
    expect(within(machines).queryByRole('link')).toBeNull()
    const facts = (name: string) =>
      [...screen.getByRole('group', { name }).querySelectorAll('dt')].map((dt) => `${dt.textContent}: ${dt.nextElementSibling!.textContent}`)
    expect(facts('Washing machine')).toEqual(['State: Off', 'Door: Closed', 'ConnectLife: Online'])
    expect(facts('Tumble dryer')).toEqual(['State: Off', 'Door: Open', 'ConnectLife: Offline'])
  })

  it('Apple devices shows the house, then every device per room with its state', async () => {
    stubApi({ '/api/apple': APPLE })
    renderRoute('/home/apple')

    expect(await screen.findByRole('region', { name: 'The house' })).toHaveTextContent('1 offline')
    const bedroom = screen.getByRole('group', { name: 'Bedroom' })
    expect(bedroom).toHaveTextContent('Bedroom miniHomePod mini · Thread border routerOffline, went off 2 hours ago')
    expect(screen.getByRole('group', { name: 'Living room' })).toHaveTextContent('Living TVApple TV · Thread border routerOnline')
  })

  it('Outside holds the status pages and says a problem once in its header; Services no longer lists them', async () => {
    stubApi({ '/api/services': SERVICES, '/api/outside-services': outsideServices({ github: ACTIONS_DELAYED }) })
    const { unmount } = renderRoute('/house/outside')

    expect(await screen.findByRole('region', { name: 'Outside services' })).toBeInTheDocument()
    expect(screen.getByText('1 with a problem')).toBeInTheDocument()
    unmount()

    renderRoute('/house/services')
    expect(await screen.findByRole('heading', { level: 1, name: 'Services' })).toBeInTheDocument()
    expect(screen.queryByRole('region', { name: 'Outside services' })).toBeNull()
  })
})
