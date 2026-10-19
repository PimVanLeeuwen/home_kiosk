import { act, render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { vi } from 'vitest'
import type { Music } from '../../lib/musicTypes'
import { stubApi } from '../../test/stubApi'
import { NowPlayingCard } from './NowPlayingCard'

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
      <NowPlayingCard />
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
