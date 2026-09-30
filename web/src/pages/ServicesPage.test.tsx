import { act, fireEvent, screen, within } from '@testing-library/react'
import { vi } from 'vitest'
import type { ServicesResponse } from '../lib/types'
import { renderRoute } from '../test/renderRoute'
import { stubApi } from '../test/stubApi'

const SERVICES: ServicesResponse = {
  as_of: '2026-09-30T12:00:00Z',
  stale: false,
  groups: [
    {
      name: 'Media',
      services: [
        {
          id: 'jellyfin',
          name: 'Jellyfin',
          group: 'Media',
          description: 'Media server',
          port: 8096,
          path: '/',
          container: 'jellyfin',
          widget: 'jellyfin',
          status: 'up',
        },
        {
          id: 'immich',
          name: 'Immich',
          group: 'Media',
          description: 'Photos',
          port: 2283,
          path: '/',
          container: 'immich_server',
          widget: 'immich',
          status: 'unhealthy',
        },
      ],
    },
    {
      name: 'Apps',
      services: [
        {
          id: 'couchdb',
          name: 'CouchDB',
          group: 'Apps',
          description: 'Obsidian LiveSync',
          port: 5984,
          path: '/_utils',
          container: 'couchdb',
          widget: null,
          status: 'down',
        },
      ],
    },
  ],
}

const HOSTS = {
  as_of: '2026-09-30T12:00:00Z',
  stale: false,
  lan: '192.168.1.10',
  tailscale: { dns_name: 'dev-minotaur.tail1234.ts.net', ip: '100.70.0.10' },
}

describe('ServicesPage', () => {
  afterEach(() => vi.useRealTimers())

  it('shows a loading state first', () => {
    stubApi({ '/api/services': () => new Promise(() => {}) as unknown })
    renderRoute('/services')

    expect(screen.getByRole('status')).toHaveTextContent('Loading services')
  })

  it('groups services with their status and a count of running ones', async () => {
    stubApi({ '/api/services': SERVICES, '/api/hosts': HOSTS })
    renderRoute('/services')

    const media = await screen.findByRole('region', { name: 'Media' })
    expect(screen.getByText('1 of 3 running')).toBeInTheDocument()
    expect(screen.getByRole('region', { name: 'Apps' })).toBeInTheDocument()

    const jellyfin = within(media).getByRole('link', { name: /Jellyfin/ })
    expect(jellyfin).toHaveAccessibleName(/Running/)
    expect(jellyfin).toHaveAttribute('target', '_blank')
    expect(within(media).getByRole('link', { name: /Immich/ })).toHaveAccessibleName(/Unhealthy/)
    expect(screen.getByRole('link', { name: /CouchDB/ })).toHaveAccessibleName(/Stopped/)
  })

  it('links to the NAS LAN address when the hub runs on this computer', async () => {
    stubApi({ '/api/services': SERVICES, '/api/hosts': HOSTS })
    renderRoute('/services')

    // jsdom serves the page from localhost, so the /api/hosts LAN address applies.
    const couchdb = await screen.findByRole('link', { name: /CouchDB/ })
    await vi.waitFor(() =>
      expect(couchdb).toHaveAttribute('href', 'http://192.168.1.10:5984/_utils'),
    )
  })

  it('says when the container status is stale', async () => {
    stubApi({ '/api/services': { ...SERVICES, stale: true } })
    renderRoute('/services')

    expect(await screen.findByText(/Status may be out of date/)).toBeInTheDocument()
  })

  it('offers a retry when the API does not answer', async () => {
    const fetchMock = stubApi({ '/api/services': new Error('offline') })
    renderRoute('/services')

    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent('The hub API is not answering')

    stubApi({ '/api/services': SERVICES })
    fireEvent.click(within(alert).getByRole('button', { name: 'Try again' }))

    expect(await screen.findByRole('region', { name: 'Media' })).toBeInTheDocument()
    expect(fetchMock).toHaveBeenCalled()
  })

  it('keeps the last services when a refresh fails', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    let fail = false
    stubApi({ '/api/services': () => (fail ? new Error('offline') : SERVICES) })
    renderRoute('/services')
    await screen.findByRole('region', { name: 'Media' })

    fail = true
    await act(() => vi.advanceTimersByTimeAsync(30_000))

    expect(screen.getByRole('region', { name: 'Media' })).toBeInTheDocument()
    expect(screen.getByText(/Status may be out of date/)).toBeInTheDocument()
  })
})
