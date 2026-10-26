import { act, fireEvent, screen, waitFor } from '@testing-library/react'
import { RECENT_KEY, shortcutLabel } from '../lib/palette'
import { renderRoute } from '../test/renderRoute'
import { failWith, stubApi } from '../test/stubApi'

const palette = () => document.querySelector<HTMLDialogElement>('dialog[aria-label="Search the hub"]')!
const field = () => screen.getByRole('combobox', { name: 'Search', hidden: true })
const selected = () => screen.getAllByRole('option', { hidden: true }).find((o) => o.getAttribute('aria-selected') === 'true')

function openWithKeys() {
  act(() => {
    fireEvent.keyDown(window, { key: 'k', ctrlKey: true })
  })
}

beforeEach(() => localStorage.clear())

describe('CommandPalette', () => {
  it('opens with Ctrl-K or ⌘K, and the same keys close it', () => {
    renderRoute('/')
    expect(palette().open).toBe(false)

    openWithKeys()
    expect(palette().open).toBe(true)
    expect(screen.getByRole('option', { name: /^Lights on/, hidden: true })).toHaveAttribute('aria-selected', 'true')

    act(() => {
      fireEvent.keyDown(window, { key: 'K', metaKey: true })
    })
    expect(palette().open).toBe(false)
  })

  it('stays open when a close from before it opened again arrives late', () => {
    renderRoute('/')
    openWithKeys()
    openWithKeys()
    openWithKeys()
    expect(palette().open).toBe(true)

    act(() => {
      palette().dispatchEvent(new Event('close'))
    })
    expect(palette().open).toBe(true)
  })

  it('opens from the sidebar and the phone’s search button', () => {
    renderRoute('/')

    fireEvent.click(screen.getByRole('button', { name: /^Search\s*(⌘K|Ctrl K)$/ }))
    expect(palette().open).toBe(true)
    act(() => palette().close())
    fireEvent.click(screen.getByRole('button', { name: 'Search' }))
    expect(palette().open).toBe(true)
  })

  it('finds by a few letters, moves with the arrows and goes with Enter', () => {
    const { router } = renderRoute('/')
    openWithKeys()

    fireEvent.change(field(), { target: { value: 'bk' } })
    expect(selected()).toHaveTextContent('Backups')
    expect(field()).toHaveAttribute('aria-activedescendant', selected()!.id)

    fireEvent.keyDown(field(), { key: 'ArrowUp' })
    const last = screen.getAllByRole('option', { hidden: true }).at(-1)
    expect(selected()).toBe(last)
    fireEvent.keyDown(field(), { key: 'ArrowDown' })
    fireEvent.keyDown(field(), { key: 'Enter' })

    expect(router.state.location.pathname).toBe('/backups')
    expect(palette().open).toBe(false)
    expect(JSON.parse(localStorage.getItem(RECENT_KEY)!)).toEqual(['page:/backups'])
  })

  it('goes to a Settings section on a click, and shows it as recent next time', () => {
    const { router } = renderRoute('/')
    openWithKeys()
    fireEvent.change(field(), { target: { value: 'desk' } })
    fireEvent.click(screen.getByRole('option', { name: /Desk panels/, hidden: true }))
    expect(router.state.location.pathname).toBe('/settings/desk-panels')

    openWithKeys()
    expect(field()).toHaveValue('')
    expect(screen.getByText('Recent')).toBeInTheDocument()
    expect(selected()).toHaveTextContent('Desk panels')
  })

  it('says when nothing matches', () => {
    renderRoute('/')
    openWithKeys()

    fireEvent.change(field(), { target: { value: 'zzzz' } })

    expect(screen.getByText('Nothing found for “zzzz”.')).toBeInTheDocument()
    expect(field()).toHaveAttribute('aria-expanded', 'false')
  })

  it('writes the shortcut the way the computer does', () => {
    expect(shortcutLabel('MacIntel')).toBe('⌘K')
    expect(shortcutLabel('Win32')).toBe('Ctrl K')
  })

  it('finds a service once the palette has asked for them, and opens it in a new tab', async () => {
    stubApi({
      '/api/services': { as_of: null, stale: false, groups: [{ name: 'Media', services: [
        { id: 'jellyfin', name: 'Jellyfin', group: 'Media', description: 'Media server', port: 8096, path: '/', container: 'jellyfin', widget: null, icon: 'jellyfin', status: 'up' },
      ] }] },
    })
    const open = vi.spyOn(window, 'open').mockReturnValue(null)
    renderRoute('/')
    openWithKeys()

    fireEvent.change(field(), { target: { value: 'jelly' } })
    const option = await screen.findByRole('option', { name: /Jellyfin/, hidden: true })
    expect(option).toHaveTextContent('Media server')
    fireEvent.keyDown(field(), { key: 'Enter' })

    expect(open).toHaveBeenCalledWith(expect.stringMatching(/:8096\/$/), '_blank', 'noopener,noreferrer')
    expect(palette().open).toBe(false)
  })

  it('runs an action, says it worked and then closes', async () => {
    const fetchMock = stubApi({ 'POST /api/lights/room': { groups: [] } })
    renderRoute('/')
    openWithKeys()

    fireEvent.change(field(), { target: { value: 'lights off' } })
    fireEvent.keyDown(field(), { key: 'Enter' })

    expect(await screen.findByText('The living room lights are off.')).toBeInTheDocument()
    const post = fetchMock.mock.calls.find(([, init]) => init?.method === 'POST')!
    expect(post[0]).toBe('/api/lights/room')
    expect(JSON.parse(String(post[1]!.body))).toEqual({ on: false })
    await waitFor(() => expect(palette().open).toBe(false))
  })

  it('stays open with the hub’s reason when an action fails', async () => {
    stubApi({ 'POST /api/music/control/pause': failWith(409, { detail: 'Nothing is playing.' }) })
    renderRoute('/')
    openWithKeys()

    fireEvent.change(field(), { target: { value: 'pause' } })
    fireEvent.keyDown(field(), { key: 'Enter' })

    expect(await screen.findByText('Pause did not work: Nothing is playing.')).toBeInTheDocument()
    expect(palette().open).toBe(true)
  })

  it('asks Paperless once typing pauses, and lists its documents after the hub’s own rows', async () => {
    const fetchMock = stubApi({
      '/api/services': { as_of: null, stale: false, groups: [{ name: 'Apps', services: [
        { id: 'paperless', name: 'Paperless', group: 'Apps', description: 'Documents', port: 8010, path: '/', container: 'paperless', widget: 'paperless', icon: null, status: 'up' },
      ] }] },
      '/api/documents/search?q=water': { as_of: '', stale: false, available: true, reason: null, results: [
        { id: 41, title: 'Jaaropgave 2025', correspondent: 'Brabant Water', created: '2026-02-14' },
      ] },
    })
    renderRoute('/')
    openWithKeys()

    fireEvent.change(field(), { target: { value: 'wa' } })
    fireEvent.change(field(), { target: { value: 'water' } })

    const doc = await screen.findByRole('option', { name: /Jaaropgave 2025/, hidden: true })
    expect(doc).toHaveTextContent('Brabant Water · 14 Feb 2026')
    const asked = fetchMock.mock.calls.map(([path]) => String(path)).filter((p) => p.startsWith('/api/documents'))
    expect(asked).toEqual(['/api/documents/search?q=water'])
  })

  it('says why there are no documents when Paperless does not answer', async () => {
    stubApi({ '/api/documents/search?q=bill': { as_of: '', stale: false, available: false, reason: 'Not reachable', results: [] } })
    renderRoute('/')
    openWithKeys()

    fireEvent.change(field(), { target: { value: 'bill' } })

    expect(await screen.findByText('Paperless: Not reachable')).toBeInTheDocument()
  })
})
