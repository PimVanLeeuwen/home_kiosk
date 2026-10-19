import { act, fireEvent, screen, within } from '@testing-library/react'
import { vi } from 'vitest'
import type { Music, Playing } from '../lib/musicTypes'
import { renderRoute } from '../test/renderRoute'
import { failWith, sentBody, stubApi } from '../test/stubApi'

const device = (id: string, name: string, active = false) => ({ id, name, type: 'tv', active, volume: 60, restricted: false })
const PLAYING: Playing = {
  kind: 'track',
  title: 'Midnight City',
  subtitle: 'M83 · Hurry Up',
  duration_ms: 243000,
  cover: 'c1',
  colour: '#e85c8c',
  state: 'playing',
  progress_ms: 97000,
  device: device('atv', 'Apple TV Living Room', true),
}

function music(over: Partial<Music> = {}): Music {
  return {
    as_of: 1,
    stale: false,
    connected: true,
    default_device: 'Apple TV Living Room',
    playing: PLAYING,
    devices: [device('atv', 'Apple TV Living Room', true), device('mac', 'MacBook Pro')],
    favourites: [{ position: 0, id: 'p1', name: 'Discover Weekly', cover: null, colour: null }],
    last: null,
    ...over,
  }
}

describe('MusicPage', () => {
  it('shows what plays with its cover, progress, device and the favourites', async () => {
    stubApi({ '/api/music': music() })
    renderRoute('/music')

    const now = await screen.findByRole('region', { name: 'Now playing' })
    expect(within(now).getByRole('heading', { name: 'Midnight City' })).toBeInTheDocument()
    expect(now).toHaveAttribute('data-state', 'playing')
    expect(within(now).getByText('Apple TV Living Room')).toBeInTheDocument()
    expect(within(now).getByRole('progressbar')).toHaveAttribute('aria-valuetext', '1:37 of 4:03')
    expect(within(now).getByRole('slider', { name: 'Volume' })).toHaveValue('60')
    expect(now.querySelector('img')).toHaveAttribute('src', '/api/music/covers/c1')
    const side = screen.getByRole('region', { name: 'Devices and favourites' })
    expect(within(side).getByRole('button', { name: 'Apple TV Living Room: playing here' })).toBeDisabled()
    expect(within(side).getByRole('button', { name: 'Play Discover Weekly' })).toBeEnabled()
  })

  it('pauses at once and holds it while Spotify still reports playing', async () => {
    const fetchMock = stubApi({ '/api/music': music(), 'POST /api/music/control/pause': { ok: true } })
    renderRoute('/music')

    fireEvent.click(await screen.findByRole('button', { name: 'Pause' }))

    expect(await screen.findByRole('button', { name: 'Play' })).toBeInTheDocument()
    expect(screen.getByRole('region', { name: 'Now playing' })).toHaveAttribute('data-state', 'paused')
    await vi.waitFor(() => expect(sentBody(fetchMock, 'POST', '/api/music/control/pause')).toEqual({}))
  })

  it('moves playback to another device', async () => {
    const fetchMock = stubApi({ '/api/music': music(), 'POST /api/music/transfer': { ok: true } })
    renderRoute('/music')

    fireEvent.click(await screen.findByRole('button', { name: 'Move playback to MacBook Pro' }))

    await vi.waitFor(() => expect(sentBody(fetchMock, 'POST', '/api/music/transfer')).toEqual({ device_id: 'mac' }))
    expect(screen.getByRole('button', { name: 'MacBook Pro: playing here' })).toBeInTheDocument()
  })

  it('sends a volume once the slider rests', async () => {
    const fetchMock = stubApi({ '/api/music': music(), 'PUT /api/music/volume': { ok: true } })
    renderRoute('/music')
    const slider = await screen.findByRole('slider', { name: 'Volume' })

    vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout'] })
    try {
      fireEvent.change(slider, { target: { value: '40' } })
      fireEvent.change(slider, { target: { value: '30' } })
      await act(() => vi.advanceTimersByTimeAsync(350))
    } finally {
      vi.useRealTimers()
    }

    await vi.waitFor(() => expect(sentBody(fetchMock, 'PUT', '/api/music/volume')).toEqual({ percent: 30 }))
    expect(fetchMock.mock.calls.filter(([, init]) => init?.method === 'PUT')).toHaveLength(1)
  })

  it('starts a favourite and says when the Apple TV could not be woken', async () => {
    const fetchMock = stubApi({
      '/api/music': music({ playing: null }),
      'POST /api/music/favourites/0/play': failWith(409, { detail: 'Apple TV Living Room is not available in Spotify: open Spotify on it first.' }),
    })
    renderRoute('/music')

    expect(await screen.findByRole('heading', { name: 'Nothing playing' })).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Play Discover Weekly' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('open Spotify on it first')
    expect(sentBody(fetchMock, 'POST', '/api/music/favourites/0/play')).toEqual({})
  })

  it('shows what played last when nothing plays, and the stale note', async () => {
    stubApi({ '/api/music': music({ playing: null, stale: true, last: { ...PLAYING, title: 'Wait' } }) })
    renderRoute('/music')

    expect(await screen.findByText('Wait')).toBeInTheDocument()
    expect(screen.getByText('Showing the last known figures.')).toBeInTheDocument()
  })

  it('points to Settings while Spotify is not connected, and explains a failure', async () => {
    stubApi({ '/api/music': music({ connected: false, playing: null }) })
    const { unmount } = renderRoute('/music')
    expect(await screen.findByRole('link', { name: 'Settings → Music' })).toHaveAttribute('href', '/settings#music')
    unmount()

    stubApi({ '/api/music': failWith(503, { detail: 'Spotify is not set up (SPOTIFY_CLIENT_ID).' }) })
    renderRoute('/music')
    expect(await screen.findByRole('alert')).toHaveTextContent('SPOTIFY_CLIENT_ID')
  })
})
