import { vi } from 'vitest'
import { fireEvent, screen, within } from '@testing-library/react'
import { iconUrl } from '../lib/icons'
import type { CatalogService, SettingsCatalog } from '../lib/types'
import { renderRoute } from '../test/renderRoute'
import { failWith, sentBody, stubApi } from '../test/stubApi'

const svc = (id: string, name: string, group: string, extra: Partial<CatalogService> = {}) => ({
  id,
  name,
  group,
  description: '',
  port: 8000,
  path: '/',
  container: null,
  widget: null,
  ...extra,
})

const CATALOG: SettingsCatalog = {
  services: [
    svc('jellyfin', 'Jellyfin', 'Media', { port: 8096, container: 'jellyfin', widget: 'jellyfin' }),
    svc('immich', 'Immich', 'Media', { port: 2283 }),
    svc('couchdb', 'CouchDB', 'Apps', { port: 5984, path: '/_utils' }),
  ],
  widgets: ['immich', 'jellyfin'],
}

const CONTAINERS = {
  as_of: '2026-09-30T12:00:00Z',
  stale: false,
  containers: [{ name: 'uptime-kuma', state: 'running', health: null }],
}

const ENDPOINT = '/api/settings/services'

function setup(extra: Record<string, unknown> = {}) {
  const fetchMock = stubApi({ [ENDPOINT]: CATALOG, '/api/containers': CONTAINERS, ...extra })
  renderRoute('/settings')
  return fetchMock
}

describe('SettingsPage services', () => {
  it('lists the catalog by group with port, path, container and widget', async () => {
    setup()

    const media = await screen.findByRole('region', { name: 'Media' })
    expect(within(media).getByText('Jellyfin')).toBeInTheDocument()
    expect(within(media).getByText(/jellyfin widget/)).toBeInTheDocument()
    expect(screen.getByText(':5984/_utils')).toBeInTheDocument()
    expect(screen.getByText('3 services in 2 groups.', { exact: false })).toBeInTheDocument()
  })

  it('adds a service and shows the new catalog', async () => {
    const added = { ...CATALOG, services: [...CATALOG.services, svc('uptime-kuma', 'Uptime Kuma', 'Monitoring')] }
    const fetchMock = setup({ [`POST ${ENDPOINT}`]: added })
    fireEvent.click(await screen.findByRole('button', { name: 'Add service' }))

    const form = screen.getByRole('form', { name: 'Add a service' })
    fireEvent.change(within(form).getByLabelText('Name'), { target: { value: 'Uptime Kuma' } })
    fireEvent.change(within(form).getByLabelText('Group'), { target: { value: 'Monitoring' } })
    fireEvent.change(within(form).getByLabelText('Port'), { target: { value: '3001' } })
    fireEvent.change(within(form).getByLabelText('Container (for the status dot)'), {
      target: { value: 'uptime-kuma' },
    })
    fireEvent.submit(form)

    expect(await screen.findByRole('region', { name: 'Monitoring' })).toBeInTheDocument()
    expect(screen.queryByRole('form', { name: 'Add a service' })).not.toBeInTheDocument()
    expect(sentBody(fetchMock, 'POST', ENDPOINT)).toEqual({
      name: 'Uptime Kuma',
      group: 'Monitoring',
      description: '',
      port: 3001,
      path: '/',
      url: null,
      container: 'uptime-kuma',
      widget: null,
      icon: null,
    })
  })

  it('adds a link with only the fields a link needs', async () => {
    const withLink = {
      ...CATALOG,
      services: [...CATALOG.services, svc('trash-guides', 'TRaSH Guides', 'Links', { port: null, url: 'https://trash-guides.info' })],
    }
    const fetchMock = setup({ [`POST ${ENDPOINT}`]: withLink })
    fireEvent.click(await screen.findByRole('button', { name: 'Add service' }))

    const form = screen.getByRole('form', { name: 'Add a service' })
    fireEvent.click(within(form).getByLabelText('Link to a website'))
    expect(within(form).queryByLabelText('Port')).not.toBeInTheDocument()
    fireEvent.change(within(form).getByLabelText('Name'), { target: { value: 'TRaSH Guides' } })
    fireEvent.change(within(form).getByLabelText('Group'), { target: { value: 'Links' } })
    fireEvent.change(within(form).getByLabelText('Address'), { target: { value: 'https://trash-guides.info' } })
    fireEvent.submit(form)

    expect(await screen.findByText('https://trash-guides.info')).toBeInTheDocument()
    expect(sentBody(fetchMock, 'POST', ENDPOINT)).toEqual({
      name: 'TRaSH Guides',
      group: 'Links',
      description: '',
      port: null,
      path: '/',
      url: 'https://trash-guides.info',
      container: null,
      widget: null,
      icon: null,
    })
  })

  it('picks an icon, with a preview', async () => {
    const fetchMock = setup({ [`PUT ${ENDPOINT}/immich`]: CATALOG })
    fireEvent.click(await screen.findByRole('button', { name: 'Edit Immich' }))

    const form = screen.getByRole('form', { name: 'Edit Immich' })
    fireEvent.change(within(form).getByLabelText('Icon'), { target: { value: 'immich' } })
    expect(form.querySelector('img')).toHaveAttribute('src', iconUrl('immich'))
    fireEvent.submit(form)

    await vi.waitFor(() =>
      expect(sentBody(fetchMock, 'PUT', `${ENDPOINT}/immich`)).toMatchObject({ icon: 'immich' }),
    )
  })

  it('keeps the form open with the reason when the hub refuses it', async () => {
    setup({
      [`POST ${ENDPOINT}`]: failWith(422, {
        detail: [{ loc: ['body', 'container'], msg: 'Value error, must be a Docker container name' }],
      }),
    })
    fireEvent.click(await screen.findByRole('button', { name: 'Add service' }))
    const form = screen.getByRole('form', { name: 'Add a service' })
    fireEvent.change(within(form).getByLabelText('Name'), { target: { value: 'X' } })
    fireEvent.change(within(form).getByLabelText('Port'), { target: { value: '1' } })
    fireEvent.submit(form)

    expect(await within(form).findByRole('alert')).toHaveTextContent(
      'container: must be a Docker container name',
    )
    expect(within(form).getByRole('button', { name: 'Add service' })).toBeEnabled()
  })

  it('edits a service in place', async () => {
    const renamed = {
      ...CATALOG,
      services: CATALOG.services.map((s) => (s.id === 'immich' ? { ...s, description: 'Photos' } : s)),
    }
    const fetchMock = setup({ [`PUT ${ENDPOINT}/immich`]: renamed })
    fireEvent.click(await screen.findByRole('button', { name: 'Edit Immich' }))

    const form = screen.getByRole('form', { name: 'Edit Immich' })
    expect(within(form).getByLabelText('Port')).toHaveValue(2283)
    fireEvent.change(within(form).getByLabelText('Description'), { target: { value: 'Photos' } })
    fireEvent.submit(form)

    expect(await screen.findByRole('button', { name: 'Edit Immich' })).toBeInTheDocument()
    expect(screen.queryByRole('form', { name: 'Edit Immich' })).not.toBeInTheDocument()
    expect(sentBody(fetchMock, 'PUT', `${ENDPOINT}/immich`)).toMatchObject({
      name: 'Immich',
      description: 'Photos',
      port: 2283,
    })
  })

  it('asks before deleting', async () => {
    const without = { ...CATALOG, services: CATALOG.services.filter((s) => s.id !== 'immich') }
    const fetchMock = setup({ [`DELETE ${ENDPOINT}/immich`]: without })
    fireEvent.click(await screen.findByRole('button', { name: 'Delete Immich' }))

    expect(screen.getByText('Delete Immich?')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Cancel' }))
    expect(fetchMock.mock.calls.some(([, init]) => init?.method === 'DELETE')).toBe(false)

    fireEvent.click(screen.getByRole('button', { name: 'Delete Immich' }))
    fireEvent.click(screen.getByRole('button', { name: 'Delete' }))

    await screen.findByText('2 services in 2 groups.', { exact: false })
    expect(screen.queryByText('Immich')).not.toBeInTheDocument()
  })

  it('moves services within their group and groups as a whole', async () => {
    const fetchMock = setup({ [`PUT /api/settings/services-order`]: CATALOG })
    await screen.findByRole('region', { name: 'Media' })

    expect(screen.getByRole('button', { name: 'Move Jellyfin up' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Move group Media up' })).toBeDisabled()

    fireEvent.click(screen.getByRole('button', { name: 'Move Jellyfin down' }))
    await vi.waitFor(() =>
      expect(sentBody(fetchMock, 'PUT', '/api/settings/services-order')).toEqual({
        ids: ['immich', 'jellyfin', 'couchdb'],
      }),
    )

    fireEvent.click(screen.getByRole('button', { name: 'Move group Apps up' }))
    await vi.waitFor(() =>
      expect(sentBody(fetchMock, 'PUT', '/api/settings/services-order', 1)).toEqual({
        ids: ['couchdb', 'jellyfin', 'immich'],
      }),
    )
  })

  it('renames a group', async () => {
    const renamed = {
      ...CATALOG,
      services: CATALOG.services.map((s) => (s.group === 'Apps' ? { ...s, group: 'Tools' } : s)),
    }
    const fetchMock = setup({ 'PUT /api/settings/groups': renamed })
    fireEvent.click(await screen.findByRole('button', { name: 'Rename group Apps' }))

    const form = screen.getByRole('form', { name: 'Rename group Apps' })
    fireEvent.change(within(form).getByLabelText('Group name'), { target: { value: 'Tools' } })
    fireEvent.submit(form)

    expect(await screen.findByRole('region', { name: 'Tools' })).toBeInTheDocument()
    expect(sentBody(fetchMock, 'PUT', '/api/settings/groups')).toEqual({ old: 'Apps', new: 'Tools' })
  })

  it('shows list action failures', async () => {
    setup({ 'PUT /api/settings/services-order': failWith(409, { detail: 'The order must list every service exactly once.' }) })
    fireEvent.click(await screen.findByRole('button', { name: 'Move Jellyfin down' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('every service exactly once')
  })

  it('says when the catalog cannot be loaded', async () => {
    stubApi({})
    renderRoute('/settings')

    expect(await screen.findByRole('alert')).toHaveTextContent('could not be loaded')
  })
})
