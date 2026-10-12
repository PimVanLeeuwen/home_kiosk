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

    // The outside services section below has a loading state of its own.
    expect(screen.getAllByRole('status')[0]).toHaveTextContent('Loading services')
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

  it('sums up with a pill, a dot per service, and a tinted count and tile per problem', async () => {
    stubApi({ '/api/services': SERVICES, '/api/hosts': HOSTS })
    renderRoute('/services')

    const media = await screen.findByRole('region', { name: 'Media' })
    expect(screen.getByText('2 need a look', { selector: '.uppercase' })).toBeInTheDocument()
    const summary = screen.getByRole('region', { name: 'Running' })
    expect(summary).toHaveTextContent('1 / 3 running')
    expect([...summary.querySelectorAll('[data-status]')].map((d) => d.getAttribute('data-status'))).toEqual(['up', 'unhealthy', 'down'])
    // Media holds one unhealthy service: an amber count; Apps a stopped one: red.
    expect(media.querySelector('[data-tone]')).toHaveAttribute('data-tone', 'warn')
    expect(screen.getByRole('region', { name: 'Apps' }).querySelector('[data-tone]')).toHaveAttribute('data-tone', 'down')
    expect(within(media).getByRole('link', { name: /Immich/ })).toHaveAttribute('data-trouble', 'warn')
    const couchdb = screen.getByRole('link', { name: /CouchDB/ })
    expect(couchdb).toHaveAttribute('data-trouble', 'down')
    expect(couchdb).toHaveTextContent('Stopped')
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

  it('shows live stats instead of the description, and flags stats errors', async () => {
    const withStats: ServicesResponse = {
      ...SERVICES,
      groups: [
        {
          ...SERVICES.groups[0],
          services: [
            {
              ...SERVICES.groups[0].services[0],
              stats: [
                { label: 'Streaming', value: 2, unit: 'count' },
                { label: 'Movies', value: 1812, unit: 'count' },
              ],
            },
            { ...SERVICES.groups[0].services[1], stats: null, stats_error: 'No API key set (IMMICH_API_KEY)' },
          ],
        },
        SERVICES.groups[1],
      ],
    }
    stubApi({ '/api/services': withStats })
    renderRoute('/services')

    const jellyfin = await screen.findByRole('link', { name: /Jellyfin/ })
    expect(jellyfin).toHaveTextContent('2 streaming · 1.812 movies')
    expect(jellyfin).not.toHaveTextContent('Media server')

    const immich = screen.getByRole('link', { name: /Immich/ })
    expect(immich).toHaveTextContent('Photos')
    expect(immich).toHaveAccessibleName(/Stats unavailable: No API key set \(IMMICH_API_KEY\)/)
  })

  it('shows links without a status and leaves them out of the count', async () => {
    const withLink: ServicesResponse = {
      ...SERVICES,
      groups: [
        ...SERVICES.groups,
        {
          name: 'Links',
          services: [
            {
              id: 'trash-guides', name: 'TRaSH Guides', group: 'Links', description: 'Guides',
              port: null, path: '/', url: 'https://trash-guides.info', container: null,
              widget: null, status: 'unknown',
            },
          ],
        },
      ],
    }
    stubApi({ '/api/services': withLink })
    renderRoute('/services')

    const link = await screen.findByRole('link', { name: /TRaSH Guides/ })
    expect(link).toHaveAttribute('href', 'https://trash-guides.info')
    expect(link).not.toHaveAccessibleName(/Status unknown/)
    expect(screen.getByText('1 of 3 running')).toBeInTheDocument()
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
