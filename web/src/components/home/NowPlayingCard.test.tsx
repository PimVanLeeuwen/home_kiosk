import { act, render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { vi } from 'vitest'
import type { Music } from '../../lib/musicTypes'
import { stubApi } from '../../test/stubApi'
import { useHomeNowPlaying } from '../../lib/useHomeNowPlaying'
import { NowPlayingCard } from './NowPlayingCard'

/** The card as Home gives it what plays. */
function Home() {
  const { playing, send, pausedUntil } = useHomeNowPlaying()
  return <NowPlayingCard playing={playing} send={send} pausedUntil={pausedUntil} />
}

const playing = (state: 'playing' | 'paused') => ({
  kind: 'track' as const,
  title: 'Midnight City',
  subtitle: 'M83',
  duration_ms: 243000,
  cover: null,
  colour: null,
  state,
  progress_ms: 97000,
  device: { id: 'atv', name: 'Apple TV Living Room', type: 'tv', active: true, volume: 60, restricted: false },
})

const music = (p: Music['playing']): Music => ({
  as_of: 1,
  stale: false,
  connected: true,
  default_device: 'Apple TV Living Room',
  playing: p,
  devices: [],
  favourites: [],
  last: null,
})

const show = () =>
  render(
    <MemoryRouter>
      <Home />
    </MemoryRouter>,
  )

describe('NowPlayingCard', () => {
  it('shows what plays on which device, with the controls', async () => {
    stubApi({ '/api/music': music(playing('playing')) })
    show()

    expect(await screen.findByRole('heading', { name: 'Midnight City' })).toBeInTheDocument()
    expect(screen.getByText('On Apple TV Living Room')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Pause' })).toBeInTheDocument()
  })

  it('says until when Spotify paused the hub, and the controls wait', async () => {
    vi.useFakeTimers({ toFake: ['Date'] })
    vi.setSystemTime(new Date(2026, 9, 25, 16, 40))
    try {
      stubApi({ '/api/music': { ...music(playing('playing')), stale: true, paused_until: new Date(2026, 9, 25, 16, 52).getTime() / 1000 } })
      show()

      expect(await screen.findByRole('status')).toHaveTextContent('Spotify paused the hub until 16:52')
      for (const name of ['Previous', 'Pause', 'Next']) expect(screen.getByRole('button', { name })).toBeDisabled()
    } finally {
      vi.useRealTimers()
    }
  })

  it('is not there while nothing plays or Spotify is not connected', async () => {
    const fetchMock = stubApi({ '/api/music': music(null) })
    const { container } = show()

    await vi.waitFor(() => expect(fetchMock).toHaveBeenCalled())
    expect(container).toBeEmptyDOMElement()
  })

  it('leaves two minutes after a pause', async () => {
    vi.useFakeTimers({ toFake: ['setInterval', 'clearInterval', 'Date'] })
    try {
      stubApi({ '/api/music': music(playing('paused')) })
      show()
      await act(() => vi.advanceTimersByTimeAsync(100))
      expect(screen.getByText(/Paused/)).toBeInTheDocument()

      await act(() => vi.advanceTimersByTimeAsync(2 * 60_000 + 10_000))
      expect(screen.queryByRole('heading', { name: 'Midnight City' })).not.toBeInTheDocument()
    } finally {
      vi.useRealTimers()
    }
  })
})
