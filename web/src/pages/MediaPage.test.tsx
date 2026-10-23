import { fireEvent, screen, within } from '@testing-library/react'
import type { Media, MediaDownload, MediaOverview } from '../lib/types'
import { renderRoute } from '../test/renderRoute'
import { stubApi } from '../test/stubApi'

const at = (day: number, hour: number) => new Date(2026, 9, day, hour).toISOString()
const download = (over: Partial<MediaDownload>): MediaDownload => ({
  id: 'sonarr:1', kind: 'tv', title: 'Harbour Lights', detail: 'S2 E5 · The Breakwater', size_bytes: 1_400_000_000,
  left_bytes: 392_000_000, progress_pct: 72, time_left_seconds: 372, client: 'SABnzbd', state: 'downloading',
  message: null, poster: 'sonarr/12', ...over,
})
const MEDIA: Media = {
  as_of: at(14, 10), stale: false, errors: {},
  downloads: [
    download({ id: 'sonarr:3', detail: 'S2 E4 · Slack Tide', progress_pct: 100, time_left_seconds: null, state: 'failed', message: 'Not enough free space' }),
    download({}),
    download({ id: 'radarr:7', kind: 'movie', title: 'Glass Harbour', detail: 'Movie · 2025', progress_pct: 31, time_left_seconds: 1440, poster: null }),
  ],
  missing: [{ series: 'Northbound', season: 3, episode: 1, title: 'Thaw', air_date: at(12, 21), poster: 'sonarr/30' }],
  missing_total: 14,
  upcoming: [
    { series: 'The Long Coast', season: 1, episode: 6, title: 'High Water', air_date: at(14, 21), poster: null },
    { series: 'Fieldwork', season: 1, episode: 1, title: 'Pilot', air_date: at(19, 21), poster: null },
  ],
}

const OVERVIEW: MediaOverview = {
  as_of: at(14, 10), stale: false, errors: {}, idle_viewers: 2,
  viewers: [{ name: 'alex', plays: 113, watch_seconds: 291_274 }, { name: 'pim', plays: 49, watch_seconds: 105_334 }],
  genres: ['Adventure', 'Action', 'Drama'],
  library: { movies: 127, shows: 27, episodes: 1564, size_bytes: 4_726_229_716_345, added_movies: 0, added_episodes: 8 },
  requests: { pending: 0, processing: 13, available: 0, completed: 58 },
  latest_requests: [
    { title: 'VisionQuest', year: '2026', kind: 'tv', by: 'pim', state: 'failed', poster: null },
    { title: 'Northbound', year: '2025', kind: 'tv', by: 'pim', state: 'downloading', poster: 'sonarr/53' },
  ],
}

function show(media: Media | null, overview: MediaOverview | null = null) {
  vi.useFakeTimers({ toFake: ['Date'] })
  vi.setSystemTime(new Date(2026, 9, 14, 10, 0))
  stubApi({ ...(media ? { '/api/media': media } : {}), ...(overview ? { '/api/media/overview': overview } : {}) })
  renderRoute('/media')
}

afterEach(() => vi.useRealTimers())

describe('MediaPage', () => {
  it('heads the page with what needs a look and three figures', async () => {
    show(MEDIA)

    expect(await screen.findByText('1 needs a look')).toBeInTheDocument()
    expect(document.title).toBe('Media · Home hub')
    expect(screen.getByRole('region', { name: 'Downloads' })).toHaveTextContent('3')
    const missing = screen.getByRole('region', { name: 'Episodes missing' })
    expect(missing).toHaveTextContent('14')
    expect(within(missing).getByText('14')).toHaveStyle({ color: 'var(--color-warn)' })
  })

  it('lists downloads with progress, time left and the reason a failed one stopped', async () => {
    show(MEDIA)

    const card = await screen.findByRole('region', { name: 'Downloading' })
    const items = within(card).getAllByRole('listitem')
    expect(items.map((i) => i.dataset.state)).toEqual(['failed', 'downloading', 'downloading'])
    expect(within(items[0]).getByText('Failed')).toBeInTheDocument()
    expect(within(items[0]).getByText('Not enough free space')).toHaveClass('text-down')
    expect(within(items[1]).getByRole('progressbar')).toHaveAttribute('aria-valuenow', '72')
    expect(within(items[1]).getByText('6 min left')).toBeInTheDocument()
    expect(within(items[2]).getByText('Movie · 2025')).toBeInTheDocument()
  })

  it('shows posters through the hub and letters when there is none or it fails', async () => {
    show(MEDIA)

    const card = await screen.findByRole('region', { name: 'Downloading' })
    const img = card.querySelector('img')!
    expect(img).toHaveAttribute('src', '/api/media/posters/sonarr/12')
    fireEvent.error(img)
    expect(within(card).getAllByText('HL').length).toBeGreaterThan(0)
    expect(within(card).getByText('GH')).toBeInTheDocument()
  })

  it('shows missing episodes with when they aired, and the week ahead by day', async () => {
    show(MEDIA)

    const missing = await screen.findByRole('region', { name: 'Missing' })
    expect(within(missing).getByText('14 episodes')).toBeInTheDocument()
    expect(within(missing).getByText('aired 1 day ago')).toBeInTheDocument()
    expect(within(missing).getByText('The newest 1 of 14.')).toBeInTheDocument()
    const next = screen.getByRole('region', { name: 'Next to air' })
    expect(within(next).getByRole('region', { name: 'Today' })).toHaveTextContent('21:00')
    expect(within(next).getByRole('region', { name: 'Monday' })).toHaveTextContent('premiere')
  })

  it('says all is quiet when nothing downloads or is missing', async () => {
    show({ ...MEDIA, downloads: [], missing: [], missing_total: 0, upcoming: [] })

    expect(await screen.findByText('All quiet')).toBeInTheDocument()
    expect(screen.getByText('Nothing downloading')).toBeInTheDocument()
    expect(screen.getByText('Nothing missing')).toBeInTheDocument()
    expect(screen.getByText('Nothing airs in the coming week.')).toBeInTheDocument()
  })

  it('says which app could not be read, and when the answer is stale', async () => {
    show({ ...MEDIA, errors: { radarr: 'HTTP 503' }, stale: true })

    expect(await screen.findByText(/Radarr could not be read \(HTTP 503\)/)).toBeInTheDocument()
    expect(screen.getByText('Showing the last known figures.')).toBeInTheDocument()
  })

  it('loads, then says when Media is not available', async () => {
    show(null)

    expect(screen.getByRole('status')).toHaveTextContent('Loading')
    expect(await screen.findByText('Media is not available right now.')).toBeInTheDocument()
  })

  it('adds requests, the 30-day leaderboard and the library when Tracearr and Seerr answer', async () => {
    show(MEDIA, OVERVIEW)

    const requests = await screen.findByRole('region', { name: 'Requests' })
    expect(within(requests).getByText('done, all time').previousElementSibling).toHaveTextContent('58')
    const items = within(requests).getAllByRole('listitem')
    expect(within(items[0]).getByText('Failed')).toHaveAttribute('data-state', 'failed')
    expect(within(items[0]).getByText('Series · 2026 · pim')).toBeInTheDocument()
    expect(items[1].querySelector('img')).toHaveAttribute('src', '/api/media/posters/sonarr/53')

    const watching = screen.getByRole('region', { name: 'Watching · 30 days' })
    const board = within(watching).getAllByRole('listitem').filter((li) => li.closest('ol'))
    expect(board.map((li) => li.textContent)).toEqual([expect.stringMatching(/^1.*alex.*80,9 h113 plays/), expect.stringMatching(/^2.*pim.*29,3 h49 plays/)])
    expect(within(watching).getByText('2 more without plays in 30 days.')).toBeInTheDocument()
    expect(within(watching).getByText('Adventure')).toBeInTheDocument()

    const library = screen.getByRole('region', { name: 'Library' })
    expect(within(library).getByText('1.564')).toBeInTheDocument()
    expect(within(library).getByText('+8 this week')).toBeInTheDocument()
    expect(within(library).getByText('4,7 TB')).toBeInTheDocument()
  })

  it('says which part could not be read, and leaves the overview out when it is not set up', async () => {
    show(MEDIA, { ...OVERVIEW, viewers: null, library: null, errors: { tracearr: 'API key refused (401)' } })

    expect(await screen.findByText('Tracearr could not be read (API key refused (401)).')).toBeInTheDocument()
    expect(screen.queryByRole('region', { name: 'Library' })).toBeNull()
  })

  it('has no overview sections without an overview answer', async () => {
    show(MEDIA)

    await screen.findByRole('region', { name: 'Downloading' })
    expect(screen.queryByRole('region', { name: 'Requests' })).toBeNull()
    expect(screen.queryByRole('region', { name: 'Watching · 30 days' })).toBeNull()
  })
})
