import { fireEvent, render, screen } from '@testing-library/react'
import { ChevronUp, Pencil, Trash2 } from 'lucide-react'
import { RowActions } from './RowActions'

const phone = (on: boolean) =>
  vi.stubGlobal('matchMedia', (query: string) => ({
    matches: on && query === '(max-width: 639px)',
    media: query,
    addEventListener: () => {},
    removeEventListener: () => {},
  }))

function setup() {
  const edit = vi.fn()
  const remove = vi.fn()
  render(
    <RowActions
      name="Jellyfin"
      actions={[
        { label: 'Move Jellyfin up', text: 'Move up', icon: ChevronUp, disabled: true, onClick: vi.fn() },
        { label: 'Edit Jellyfin', text: 'Edit', icon: Pencil, onClick: edit },
        { label: 'Delete Jellyfin', text: 'Delete', icon: Trash2, danger: true, onClick: remove },
      ]}
    />,
  )
  return { edit, remove }
}

describe('RowActions', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('shows each action as an icon button on a wide screen', () => {
    phone(false)
    const { edit } = setup()
    expect(screen.queryByRole('button', { name: 'Actions for Jellyfin' })).toBeNull()
    expect(screen.getByRole('button', { name: 'Move Jellyfin up' })).toBeDisabled()
    fireEvent.click(screen.getByRole('button', { name: 'Edit Jellyfin' }))
    expect(edit).toHaveBeenCalledOnce()
  })

  it('folds them into one menu on a phone, which closes after a choice', () => {
    phone(true)
    const { remove } = setup()
    expect(screen.queryByRole('button', { name: 'Edit Jellyfin' })).toBeNull()
    const trigger = screen.getByRole('button', { name: 'Actions for Jellyfin' })
    expect(trigger).toHaveAttribute('aria-haspopup', 'menu')

    fireEvent.click(trigger)
    expect(trigger).toHaveAttribute('aria-expanded', 'true')
    const items = screen.getAllByRole('menuitem')
    expect(items.map((i) => i.textContent)).toEqual(['Move up', 'Edit', 'Delete'])
    expect(items[0]).toBeDisabled()
    // The first action that can be taken has the focus.
    expect(items[1]).toHaveFocus()

    fireEvent.click(screen.getByRole('menuitem', { name: 'Delete Jellyfin' }))
    expect(remove).toHaveBeenCalledOnce()
    expect(screen.queryByRole('menu')).toBeNull()
    expect(trigger).toHaveFocus()
  })

  it('moves with the arrow keys and closes on Escape or a tap outside', () => {
    phone(true)
    setup()
    const trigger = screen.getByRole('button', { name: 'Actions for Jellyfin' })
    fireEvent.click(trigger)
    const menu = screen.getByRole('menu', { name: 'Actions for Jellyfin' })
    fireEvent.keyDown(menu, { key: 'ArrowDown' })
    expect(screen.getByRole('menuitem', { name: 'Delete Jellyfin' })).toHaveFocus()
    fireEvent.keyDown(menu, { key: 'ArrowDown' })
    expect(screen.getByRole('menuitem', { name: 'Edit Jellyfin' })).toHaveFocus()
    fireEvent.keyDown(menu, { key: 'Escape' })
    expect(screen.queryByRole('menu')).toBeNull()
    expect(trigger).toHaveFocus()

    fireEvent.click(trigger)
    fireEvent.pointerDown(document.body)
    expect(screen.queryByRole('menu')).toBeNull()
  })
})
