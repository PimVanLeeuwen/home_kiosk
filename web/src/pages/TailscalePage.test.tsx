import { fireEvent, screen, within } from '@testing-library/react'
import { TAILNET } from '../test/fixtures'
import { renderRoute } from '../test/renderRoute'
import { stubApi } from '../test/stubApi'

const HOSTS = {
  as_of: '2026-10-12T20:00:00Z', stale: false, lan: '192.168.1.10',
  tailscale: { dns_name: 'dev-minotaur.tail1234.ts.net', ip: '100.70.0.10', https_ports: { '8083': 443, '8096': 18096 } },
}

describe('TailscalePage', () => {
  it('heads the page with the tailnet, the online count and Healthy', async () => {
    stubApi({ '/api/tailnet': TAILNET, '/api/hosts': HOSTS })
    renderRoute('/tailscale')

    expect(await screen.findByText('tail1234 · 5 of 6 online')).toBeInTheDocument()
    expect(screen.getByText('Healthy')).toBeInTheDocument()
    expect(screen.queryByRole('alert')).toBeNull()
  })

  it('draws the map with a line per connection', async () => {
    stubApi({ '/api/tailnet': TAILNET })
    renderRoute('/tailscale')

    const map = await screen.findByRole('figure', { name: 'The NAS and 5 devices' })
    const kinds = [...map.querySelectorAll('[data-line]')].map((l) => l.getAttribute('data-line'))
    expect(kinds).toEqual(['direct', 'relay', 'direct', 'idle', 'offline'])
    // Light runs along a live connection only.
    expect(map.querySelectorAll('.motion-safe\\:animate-dash')).toHaveLength(3)
    expect(within(map).getByText('EXIT')).toBeInTheDocument()
  })

  it("shows the NAS's own names, addresses and what it serves", async () => {
    stubApi({ '/api/tailnet': TAILNET, '/api/hosts': HOSTS })
    renderRoute('/tailscale')

    const hero = await screen.findByRole('region', { name: 'Tailnet' })
    expect(within(hero).getByText('dev-minotaur.tail1234.ts.net')).toBeInTheDocument()
    expect(within(hero).getByText('100.70.0.10')).toBeInTheDocument()
    expect(within(hero).getByText('Amsterdam')).toBeInTheDocument()
    expect(await within(hero).findByText('2 hub services over HTTPS')).toBeInTheDocument()
    expect(within(hero).getByText('All checks pass')).toBeInTheDocument()
  })

  it('lists online devices first, with how they connect, then offline ones with when they were seen', async () => {
    stubApi({ '/api/tailnet': TAILNET })
    renderRoute('/tailscale')

    const online = await screen.findByRole('region', { name: /Online/ })
    expect(within(online).getAllByRole('listitem')).toHaveLength(4)
    expect(within(online).getByText('relay ams')).toBeInTheDocument()
    expect(within(online).getByText('idle')).toBeInTheDocument()
    expect(within(online).getByText('Exit node')).toBeInTheDocument()
    const offline = screen.getByRole('region', { name: /Offline/ })
    expect(within(offline).getByText('last seen 5 hours ago')).toBeInTheDocument()
    expect(within(offline).getByText('Windows')).toBeInTheDocument()
  })

  it('opens one device at a time for its details', async () => {
    stubApi({ '/api/tailnet': TAILNET })
    renderRoute('/tailscale')

    const mac = await screen.findByRole('button', { name: /pim-macbook/ })
    expect(mac).toHaveAttribute('aria-expanded', 'false')
    fireEvent.click(mac)
    expect(mac).toHaveAttribute('aria-expanded', 'true')
    expect(screen.getByText('fd7a:115c:a1e0::2')).toBeInTheDocument()
    expect(screen.getByText('192.168.1.23:41641')).toBeInTheDocument()
    expect(screen.getByText(/1,8 GB in · 412 MB out/)).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: /pim-iphone/ }))
    expect(mac).toHaveAttribute('aria-expanded', 'false')
    expect(screen.getByText('through the relay in Amsterdam')).toBeInTheDocument()
  })

  it('puts each health warning above the map and turns the pill amber', async () => {
    stubApi({ '/api/tailnet': { ...TAILNET, health: ["Tailscale can't reach the configured DNS servers."] } })
    renderRoute('/tailscale')

    expect(await screen.findByRole('alert')).toHaveTextContent("Tailscale can't reach the configured DNS servers.")
    expect(screen.getByText('1 health issue')).toBeInTheDocument()
    expect(screen.getByText('1 issue')).toHaveClass('text-warn')
  })

  it('marks a stale answer', async () => {
    stubApi({ '/api/tailnet': { ...TAILNET, stale: true } })
    renderRoute('/tailscale')

    expect(await screen.findByText('Stale')).toBeInTheDocument()
    expect(screen.getByRole('status')).toHaveTextContent('this is the last known state')
  })

  it('says so when Tailscale is not available, and loads first', async () => {
    stubApi({})
    renderRoute('/tailscale')

    expect(screen.getByRole('status')).toHaveTextContent('Loading')
    expect(await screen.findByText('Tailscale is not available right now.')).toBeInTheDocument()
  })

  it('says when the NAS is alone on the tailnet', async () => {
    stubApi({ '/api/tailnet': { ...TAILNET, peers: [] } })
    renderRoute('/tailscale')

    expect(await screen.findByText('No other devices on the tailnet yet.')).toBeInTheDocument()
    expect(screen.getByText('tail1234 · 1 of 1 online')).toBeInTheDocument()
  })
})
