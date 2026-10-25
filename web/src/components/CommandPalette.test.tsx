import { act, fireEvent, screen } from '@testing-library/react'
import { RECENT_KEY, shortcutLabel } from '../lib/palette'
import { renderRoute } from '../test/renderRoute'

const palette = () => document.querySelector<HTMLDialogElement>('dialog[aria-label="Search the hub"]')!
const field = () => screen.getByRole('combobox', { name: 'Search pages and settings', hidden: true })
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
    expect(screen.getByRole('option', { name: /^Home/, hidden: true })).toHaveAttribute('aria-selected', 'true')

    act(() => {
      fireEvent.keyDown(window, { key: 'K', metaKey: true })
    })
    expect(palette().open).toBe(false)
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
})
