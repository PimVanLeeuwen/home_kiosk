import { screen, within } from '@testing-library/react'
import { ACTIONS_DELAYED, outsideServices } from '../../test/outsideFixtures'
import { SERVICES } from '../../test/fixtures'
import { renderRoute } from '../../test/renderRoute'
import { stubApi } from '../../test/stubApi'

function home(outside: unknown) {
  stubApi({ '/api/services': SERVICES, '/api/outside-services': outside })
  renderRoute('/')
  return screen.findByRole('region', { name: 'Outside services' })
}

describe('Outside services on Home', () => {
  it('shows every service around a check when all is well', async () => {
    const card = await home(outsideServices())

    expect(await within(card).findByText('All operational')).toBeInTheDocument()
    expect(within(card).getAllByRole('listitem')).toHaveLength(7)
    expect(within(card).getByText('Cloudflare: Operational')).toBeInTheDocument()
    expect(within(card).getByRole('link', { name: /Details/ })).toHaveAttribute('href', '/services')
  })

  it('leads with the incident, its latest word and its timeline', async () => {
    await home(outsideServices({ github: ACTIONS_DELAYED }))

    // An incident lifts the card to the top, so look it up once it is there.
    const incident = await screen.findByRole('article', { name: 'GitHub: Actions runs are delayed' })
    const card = screen.getByRole('region', { name: 'Outside services' })
    expect(within(incident).getByText('Degraded')).toBeInTheDocument()
    expect(within(incident).getByText(/for 24 min/)).toBeInTheDocument()
    expect(within(incident).getByText(/a fix is rolling out/)).toBeInTheDocument()
    const steps = within(within(incident).getByRole('list', { name: 'Timeline' })).getAllByRole('listitem')
    expect(steps.map((s) => s.textContent)).toEqual([
      expect.stringMatching(/^Identified/),
      expect.stringMatching(/^Investigating/),
    ])
    expect(within(incident).getByRole('link', { name: /status page/ })).toHaveAttribute('href', 'https://stspg.io/actions')
    expect(within(card).getByText('The other 6 are operational')).toBeInTheDocument()
  })

  it('says which page could not be read, and when nothing came at all', async () => {
    const card = await home(
      outsideServices({ hetzner: { state: 'unknown', stale: true, error: 'the status page could not be reached' } }),
    )

    expect(await within(card).findByText('6 of 7 operational')).toBeInTheDocument()
    expect(within(card).getByText('Hetzner: the status page could not be reached.')).toBeInTheDocument()
  })

  it('marks a stale payload', async () => {
    const card = await home(outsideServices({}, true))
    expect(await within(card).findByText('Showing the last known figures.')).toBeInTheDocument()
  })

  it('says so when the hub has no status yet', async () => {
    const card = await home(new Error('offline'))
    expect(await within(card).findByText(/not available right now/)).toBeInTheDocument()
  })
})

describe('Outside services on the Services page', () => {
  it('lists each service with its state and the open incidents in full', async () => {
    stubApi({ '/api/services': SERVICES, '/api/outside-services': outsideServices({ github: ACTIONS_DELAYED }) })
    renderRoute('/services')

    const section = await screen.findByRole('region', { name: 'Outside services' })
    const tiles = await within(section).findAllByRole('link', { name: /Operational|Degraded/ })
    expect(tiles).toHaveLength(7)
    expect(within(section).getByRole('link', { name: 'GitHub: Degraded, open the status page' })).toHaveAttribute('href', 'https://status.github.test')
    expect(within(section).getByRole('article', { name: 'GitHub: Actions runs are delayed' })).toBeInTheDocument()
  })

  it('shows running maintenance as a calm card', async () => {
    stubApi({
      '/api/services': SERVICES,
      '/api/outside-services': outsideServices({
        cloudflare: {
          state: 'maintenance',
          incidents: [{ title: 'AMS maintenance', impact: 'maintenance', status: 'in_progress', started_at: null, url: null, updates: [] }],
        },
      }),
    })
    renderRoute('/services')

    const section = await screen.findByRole('region', { name: 'Outside services' })
    const card = await within(section).findByRole('article', { name: 'Cloudflare: AMS maintenance' })
    expect(within(card).getByText('Maintenance')).toBeInTheDocument()
  })
})
