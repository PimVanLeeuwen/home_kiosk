import { fireEvent, screen, within } from '@testing-library/react'
import type { ContainerLoad, DockerOverview } from '../lib/types'
import { renderRoute } from '../test/renderRoute'
import { stubApi } from '../test/stubApi'

const c = (name: string, project: string | null, over: Partial<ContainerLoad> = {}): ContainerLoad => ({
  name,
  project,
  image: `lscr.io/linuxserver/${name}:latest`,
  state: 'running',
  health: null,
  status: 'Up 2 days',
  cpu_pct: 1.2,
  mem_bytes: 200_000_000,
  mem_limit: 8_000_000_000,
  rx_bps: 1500,
  tx_bps: 300,
  ...over,
})

const NOW = new Date().toISOString()

const OVERVIEW: DockerOverview = {
  as_of: NOW,
  stale: false,
  cpu_pct: 14.6,
  mem_bytes: 2_400_000_000,
  containers: [
    c('sonarr', 'sonarr', { cpu_pct: 0.4, mem_bytes: 300_000_000 }),
    c('jellyfin', 'jellyfin', { cpu_pct: 12.5, mem_bytes: 900_000_000 }),
    c('gluetun', 'qbittorrent', { health: 'healthy' }),
    c('transmission', 'qbittorrent', { state: 'exited', status: 'Exited (0) 1 hour ago', cpu_pct: null, mem_bytes: null, rx_bps: null, tx_bps: null }),
    c('node-exporter', 'home_kiosk', { rx_bps: null, tx_bps: null }),
  ],
}

const UPDATES = [
  { at: NOW, name: 'sonarr', image: 'lscr.io/linuxserver/sonarr:latest', old_image_id: 'sha256:aaaaaaaaaaaaaaaa', new_image_id: 'sha256:bbbbbbbbbbbbbbbb' },
  { at: '2026-01-01T04:00:00Z', name: 'radarr', image: 'radarr', old_image_id: 'sha256:c', new_image_id: 'sha256:d' },
]

function setup(over: Record<string, unknown> = {}) {
  return stubApi({
    '/api/docker': OVERVIEW,
    '/api/docker/sparklines': { jellyfin: [1, 5, 12.5] },
    '/api/docker/updates': UPDATES,
    '/api/docker/history/jellyfin': [
      { t: '2026-10-01T10:00:00Z', cpu: 4, mem: 800_000_000 },
      { t: '2026-10-01T10:10:00Z', cpu: 12.5, mem: 900_000_000 },
    ],
    ...over,
  })
}

const names = (region: HTMLElement) =>
  within(region).getAllByRole('button', { expanded: false }).map((b) => b.querySelector('.font-mono')?.textContent)

describe('DockerPage', () => {
  it('sums up running containers, load and recent updates', async () => {
    setup()
    renderRoute('/docker')

    expect(await screen.findByText('4 of 5 running')).toBeInTheDocument()
    // One container stopped: the header says it needs a look.
    expect(screen.getByText('1 needs a look')).toBeInTheDocument()
    const tile = (name: string) => screen.getByRole('region', { name })
    expect(tile('Running')).toHaveTextContent('4 / 5')
    expect(tile('Running').querySelectorAll('i.bg-down')).toHaveLength(1)
    expect(tile('CPU, all containers')).toHaveTextContent('14,6%of the NAS')
    // The busiest containers as bars, busiest first.
    expect(within(tile('CPU, all containers')).getAllByRole('listitem').map((li) => li.textContent)).toEqual([
      'jellyfin12,5%', 'gluetun1,2%', 'node-exporter1,2%',
    ])
    expect(tile('Memory, all containers')).toHaveTextContent('2,4 GB')
    expect(within(tile('Memory, all containers')).getAllByRole('listitem')[0]).toHaveTextContent('jellyfin')
    // Only the update from today counts as the last 7 days.
    expect(tile('Updates, last 7 days')).toHaveTextContent('1image replaced')
  })

  it('says all are running, and the NAS memory when it is known', async () => {
    setup({
      '/api/docker': { ...OVERVIEW, containers: OVERVIEW.containers.filter((x) => x.state === 'running') },
      '/api/nas': { mem_total_bytes: 32e9 },
    })
    renderRoute('/docker')

    expect(await screen.findByText('All running')).toBeInTheDocument()
    expect(await within(screen.getByRole('region', { name: 'Memory, all containers' })).findByText('of 32 GB')).toBeInTheDocument()
  })

  it('groups containers by stack with a running count', async () => {
    setup()
    renderRoute('/docker')

    const torrents = await screen.findByRole('region', { name: 'qbittorrent · 1/2' })
    expect(names(torrents)).toEqual(['gluetun', 'transmission'])
    expect(within(torrents).getByRole('button', { name: /transmission/ })).toHaveTextContent('–')
    expect(screen.getByRole('region', { name: /home_kiosk/ })).toHaveTextContent('host network')
    expect(screen.getByRole('img', { name: 'jellyfin CPU, last 24 hours' })).toBeInTheDocument()
  })

  it('marks a stopped container, its stack and when it exited', async () => {
    setup()
    renderRoute('/docker')

    const torrents = await screen.findByRole('region', { name: 'qbittorrent · 1/2' })
    const stopped = within(torrents).getByRole('button', { name: /transmission/ })
    expect(stopped).toHaveTextContent('exited 1 hour ago')
    expect(stopped).toHaveClass('from-down/10')
    expect(within(torrents).getByText('1/2')).toHaveAttribute('data-tone', 'down')
    expect(within(screen.getByRole('region', { name: 'sonarr · 1/1' })).getByText('1/1')).toHaveAttribute('data-tone', 'up')
    // A running row is not tinted, and its bars compare with the busiest container.
    const jellyfin = screen.getByRole('button', { name: /jellyfin/ })
    expect(jellyfin).not.toHaveClass('from-down/10')
    const bars = [...jellyfin.querySelectorAll('[aria-hidden="true"] > span')] as HTMLElement[]
    expect(bars.map((b) => b.style.width)).toEqual(['100%', '100%'])
  })

  it('orders by CPU across stacks and filters', async () => {
    setup()
    renderRoute('/docker')
    await screen.findByText('4 of 5 running')

    fireEvent.click(within(screen.getByRole('radiogroup', { name: 'Order' })).getByRole('radio', { name: 'CPU' }))
    expect(screen.getByRole('radio', { name: 'CPU' })).toHaveAttribute('aria-checked', 'true')
    const all = screen.getByRole('region', { name: 'Containers' })
    expect(names(all).slice(0, 2)).toEqual(['jellyfin', 'gluetun'])

    fireEvent.change(screen.getByRole('searchbox', { name: 'Filter containers' }), { target: { value: 'qbit' } })
    expect(names(screen.getByRole('region', { name: 'Containers' }))).toEqual(['gluetun', 'transmission'])
  })

  it('opens a container for its 24-hour charts and details', async () => {
    const fetchMock = setup()
    renderRoute('/docker')

    fireEvent.click(await screen.findByRole('button', { name: /jellyfin/ }))

    expect(screen.getByRole('button', { name: /jellyfin/, expanded: true })).toBeInTheDocument()
    expect(await screen.findByRole('img', { name: 'jellyfin memory, last 24 hours' })).toBeInTheDocument()
    // Glowing areas with their peak marked, as on the NAS page.
    expect(document.querySelectorAll('#container-jellyfin [data-testid="peak"]')).toHaveLength(2)
    expect(screen.getByText(/peak 13%/)).toBeInTheDocument()
    expect(screen.getByText(/limit 8,0 GB/)).toBeInTheDocument()
    expect(fetchMock).toHaveBeenCalledWith('/api/docker/history/jellyfin', expect.anything())
  })

  it('lists image updates with short image ids', async () => {
    setup()
    renderRoute('/docker')

    const log = await screen.findByRole('region', { name: 'Image updates' })
    // The old and new image ids as chips, the new one lit; the newest entry's dot is lit too.
    const entries = within(log).getAllByRole('listitem')
    expect(within(entries[0]).getByText('aaaaaaaaaaaa')).not.toHaveClass('text-accent-fg')
    expect(within(entries[0]).getByText('bbbbbbbbbbbb')).toHaveClass('text-accent-fg')
    expect(entries[0].querySelector('.bg-accent-line')).not.toBeNull()
    expect(entries[1].querySelector('.bg-accent-line')).toBeNull()
    expect(within(log).getAllByText('radarr')).toHaveLength(2) // name and image
  })

  it('explains an empty update log and an unreachable collector', async () => {
    setup({ '/api/docker/updates': [] })
    renderRoute('/docker')
    expect(await screen.findByText(/No updates seen yet/)).toBeInTheDocument()
  })

  it('says when container data is not available', async () => {
    stubApi({})
    renderRoute('/docker')
    expect(await screen.findByText('Container data is not available right now.')).toBeInTheDocument()
  })
})
