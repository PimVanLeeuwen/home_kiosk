import { fireEvent, screen } from '@testing-library/react'
import { vi } from 'vitest'
import { renderRoute } from '../../test/renderRoute'
import { sentBody, stubApi } from '../../test/stubApi'

const state = (connected: boolean, favourites: { id: string; name: string }[] = []) => ({
  as_of: 1,
  stale: false,
  connected,
  default_device: 'Apple TV Living Room',
  playing: null,
  devices: [],
  favourites: favourites.map((f, position) => ({ ...f, position, cover: null, colour: null })),
  last: null,
})
const PLAYLISTS = ['Discover Weekly', 'Focus Flow', 'Sunday Morning', 'Liked Songs', 'Running Mix'].map((name, i) => ({
  id: `p${i}`,
  name,
  cover: null,
  owner: 'Spotify',
}))

describe('MusicSettings', () => {
  it('offers to connect Spotify, from the ts.net address', async () => {
    stubApi({ '/api/music': state(false) })
    renderRoute('/settings')

    expect(await screen.findByRole('link', { name: 'Connect Spotify' })).toHaveAttribute('href', '/api/music/login')
    expect(screen.getByText(/Connect from the hub's ts.net address/)).toBeInTheDocument()
  })

  it('says how connecting went when Spotify sends you back', async () => {
    stubApi({ '/api/music': state(true), '/api/music/playlists': [] })
    renderRoute('/settings?music=connected')

    expect(await screen.findByText('Spotify is connected.')).toBeInTheDocument()
  })

  it('picks up to four favourites in the order ticked, and saves them', async () => {
    const fetchMock = stubApi({
      '/api/music': state(true, [{ id: 'p0', name: 'Discover Weekly' }]),
      '/api/music/playlists': PLAYLISTS,
      'PUT /api/music/favourites': [],
    })
    renderRoute('/settings')

    expect(await screen.findByRole('checkbox', { name: /Discover Weekly/ })).toHaveAttribute('aria-checked', 'true')
    for (const name of ['Sunday Morning', 'Focus Flow', 'Liked Songs']) fireEvent.click(screen.getByRole('checkbox', { name: new RegExp(name) }))
    expect(screen.getByRole('checkbox', { name: /Running Mix/ })).toBeDisabled()
    fireEvent.click(screen.getByRole('checkbox', { name: /Discover Weekly/ }))
    fireEvent.click(screen.getByRole('checkbox', { name: /Running Mix/ }))
    fireEvent.click(screen.getByRole('button', { name: 'Save favourites' }))

    await vi.waitFor(() => expect(sentBody(fetchMock, 'PUT', '/api/music/favourites')).toEqual({ ids: ['p2', 'p1', 'p3', 'p4'] }))
    expect(await screen.findByText('Favourites saved')).toBeInTheDocument()
  })

  it('disconnects', async () => {
    const fetchMock = stubApi({ '/api/music': state(true), '/api/music/playlists': [], 'POST /api/music/disconnect': { connected: false } })
    renderRoute('/settings')

    fireEvent.click(await screen.findByRole('button', { name: 'Disconnect' }))

    await vi.waitFor(() => expect(sentBody(fetchMock, 'POST', '/api/music/disconnect')).toEqual({}))
  })
})
