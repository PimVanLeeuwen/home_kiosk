import { act, fireEvent, screen, waitFor, within } from '@testing-library/react'
import { vi } from 'vitest'
import { COOK_KEY } from '../lib/cookProgress'
import { detail } from '../test/recipeFixtures'
import { renderRoute } from '../test/renderRoute'
import { stubApi } from '../test/stubApi'

const PATH = '/api/recipes/kip-shoarma'

function wakeLock() {
  const release = vi.fn(() => Promise.resolve())
  const request = vi.fn(() => Promise.resolve({ release, addEventListener: vi.fn() }))
  vi.stubGlobal('navigator', { ...navigator, wakeLock: { request } })
  return { request, release }
}

function setup(path = '/recipes/kip-shoarma/cook?persons=4') {
  const fetchMock = stubApi({ [PATH]: detail() })
  return { fetchMock, ...renderRoute(path) }
}

const cook = () => screen.getByRole('dialog', { name: 'Cooking Kip shoarma uit de oven' })

describe('CookPage', () => {
  beforeEach(() => localStorage.clear())

  it('shows the first phase with amounts for the persons, and keeps the screen on', async () => {
    const lock = wakeLock()
    const { unmount } = setup()

    expect(await screen.findByRole('heading', { name: 'Marinade' })).toBeInTheDocument()
    expect(cook()).toHaveTextContent('prep 1 of 2')
    expect(cook()).toHaveTextContent('1 kgkippendijen')
    expect(cook()).toHaveTextContent('Next: Knoflooksaus')
    expect(await within(cook()).findByText('Screen on')).toBeInTheDocument()
    expect(cook()).toHaveTextContent('4 persons')
    expect(lock.request).toHaveBeenCalledWith('screen')
    unmount()
    expect(lock.release).toHaveBeenCalled()
  })

  it('says when the screen may sleep', async () => {
    setup()
    expect(await screen.findByText('Screen may sleep')).toBeInTheDocument()
  })

  it('folds a ticked step and keeps it on the phone', async () => {
    setup()
    const first = await screen.findByRole('button', { name: /Snijd de kippendijen/ })

    fireEvent.click(first)
    const done = screen.getByRole('button', { name: /Snijd de kippendijen/ })
    expect(done).toHaveAttribute('aria-pressed', 'true')
    expect(done.querySelector('s')).not.toBeNull()
    expect(JSON.parse(localStorage.getItem(COOK_KEY)!)['kip-shoarma'].ticks).toEqual(['0.0'])

    fireEvent.click(done)
    expect(screen.getByRole('button', { name: /Snijd de kippendijen/ })).toHaveAttribute('aria-pressed', 'false')
  })

  it('pauses before the heat, then cooks, and comes back where it was', async () => {
    const { unmount } = setup()
    fireEvent.click(await screen.findByRole('button', { name: /Snijd de kippendijen/ }))
    fireEvent.click(screen.getByRole('button', { name: 'Next phase' }))
    expect(screen.getByRole('heading', { name: 'Knoflooksaus' })).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'All prepped' }))
    const prep = screen.getByRole('list', { name: 'Prep' })
    expect(prep).toHaveTextContent('Marinade1 of 2 ticked')
    expect(prep).toHaveTextContent('Knoflooksaus0 of 1 ticked')
    expect(cook()).toHaveTextContent('First, OvenVerwarm de oven voor op 220 °C.')

    fireEvent.click(screen.getByRole('button', { name: 'Back to prep' }))
    expect(screen.getByRole('heading', { name: 'Knoflooksaus' })).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'All prepped' }))
    fireEvent.click(screen.getByRole('button', { name: 'Start cooking' }))
    expect(screen.getByRole('heading', { name: 'Oven' })).toBeInTheDocument()
    expect(cook()).toHaveTextContent('cook 1 of 2')

    unmount()
    setup()
    expect(await screen.findByRole('heading', { name: 'Oven' })).toBeInTheDocument()
  })

  it('ends on the recipe with the persons it was cooked for', async () => {
    localStorage.setItem(COOK_KEY, JSON.stringify({ 'kip-shoarma': { day: localDayNow(), version: detail().updated_at, view: 4, ticks: [] } }))
    const { router } = setup()

    fireEvent.click(await screen.findByRole('button', { name: 'Done' }))
    await waitFor(() => expect(router.state.location.pathname).toBe('/recipes/kip-shoarma'))
    expect(router.state.location.search).toBe('?persons=4')
  })

  it('closes with Escape', async () => {
    const { router } = setup('/recipes/kip-shoarma/cook')
    await screen.findByRole('heading', { name: 'Marinade' })

    await act(async () => fireEvent.keyDown(window, { key: 'Escape' }))
    await waitFor(() => expect(router.state.location.pathname).toBe('/recipes/kip-shoarma'))
    expect(router.state.location.search).toBe('')
  })
})

function localDayNow() {
  const d = new Date()
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}
