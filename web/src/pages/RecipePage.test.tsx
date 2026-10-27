import { act, fireEvent, screen, waitFor, within } from '@testing-library/react'
import { vi } from 'vitest'
import { CHECK_DELAY_MS } from '../components/recipes/PasteDialog'
import type { PasteCheck } from '../lib/recipeTypes'
import { detail, RECIPES, SHOARMA } from '../test/recipeFixtures'
import { renderRoute } from '../test/renderRoute'
import { failWith, sentBody, stubApi } from '../test/stubApi'

vi.mock('../lib/photoData', () => ({ photoData: vi.fn(() => Promise.resolve('data:image/jpeg;base64,AAAA')) }))

const PATH = '/api/recipes/kip-shoarma'

function setup(over: Record<string, unknown> = {}) {
  const fetchMock = stubApi({ [PATH]: detail(), '/api/recipes': RECIPES, ...over })
  return { fetchMock, ...renderRoute('/recipes/kip-shoarma') }
}

const menu = async (name: RegExp) => {
  fireEvent.click(await screen.findByRole('button', { name: 'Recipe actions' }))
  fireEvent.click(within(screen.getByRole('menu')).getByRole('menuitem', { name }))
}

const calls = (fetchMock: ReturnType<typeof stubApi>, path: string, method = 'GET') =>
  fetchMock.mock.calls.filter(([p, init]) => p === path && (init?.method ?? 'GET') === method).length

describe('RecipePage', () => {
  it('shows what to get, what to check and the phases, prep before the heat', async () => {
    setup()

    expect(await screen.findByRole('heading', { level: 1, name: 'Kip shoarma uit de oven' })).toBeInTheDocument()
    expect(document.title).toBe('Kip shoarma uit de oven · Home hub')
    const get = screen.getByRole('region', { name: 'To get' })
    expect(get).toHaveTextContent('Griekse yoghurt3 el + 150 g')
    expect(get).not.toHaveTextContent('komijn')
    expect(screen.getByRole('region', { name: 'Check' })).toHaveTextContent('komijn1 tl')

    const phases = screen.getAllByRole('region', { name: /, (prep|cook)$/ }).map((r) => r.getAttribute('aria-label'))
    expect(phases).toEqual(['Marinade, prep', 'Knoflooksaus, prep', 'Oven, cook', 'Afmaken, cook'])
    const line = screen.getByRole('separator', { name: 'All prepped, now the heat' })
    expect(line.compareDocumentPosition(screen.getByRole('region', { name: 'Oven, cook' })) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    expect(screen.getByRole('link', { name: 'example.com' })).toHaveAttribute('href', SHOARMA.source)
  })

  it('scales every amount with the persons', async () => {
    setup()
    const more = await screen.findByRole('button', { name: 'More persons' })

    fireEvent.click(more)
    fireEvent.click(more)
    expect(screen.getByRole('status', { name: 'Persons' })).toHaveTextContent('4')
    expect(screen.getByRole('region', { name: 'To get' })).toHaveTextContent('kippendijen1 kg')
    expect(screen.getByRole('region', { name: 'Marinade, prep' })).toHaveTextContent('½ tl kaneel')
    for (let i = 0; i < 3; i++) fireEvent.click(screen.getByRole('button', { name: 'Fewer persons' }))
    expect(screen.getByRole('button', { name: 'Fewer persons' })).toBeDisabled()
    expect(screen.getByRole('region', { name: 'To get' })).toHaveTextContent('kippendijen250 g')
  })

  it('says when a recipe does not exist', async () => {
    setup({ [PATH]: failWith(404, { detail: 'No such recipe.' }) })

    expect(await screen.findByRole('alert')).toHaveTextContent('It may have been deleted')
    expect(screen.queryByRole('button', { name: 'Try again' })).toBeNull()
    expect(within(screen.getByRole('main')).getByRole('link', { name: 'Recipes' })).toHaveAttribute('href', '/recipes')
  })

  it('copies the recipe as JSON, or with the prompt while it needs review', async () => {
    const writeText = vi.fn((text: string) => Promise.resolve(void text))
    vi.stubGlobal('navigator', { ...navigator, clipboard: { writeText } })
    setup({ [PATH]: detail({ needs_review: true }), '/api/recipes/schema': { guide: 'These are my recipes.' } })

    fireEvent.click(await screen.findByRole('button', { name: 'Copy JSON' }))
    expect(await screen.findByText(/Copied the recipe as JSON/)).toBeInTheDocument()
    expect(JSON.parse(writeText.mock.calls[0][0])).toEqual(SHOARMA)

    expect(screen.getByText('Not in phases yet')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Copy with prompt' }))
    expect(await screen.findByText(/Copied with the prompt/)).toBeInTheDocument()
    const prompt = writeText.mock.calls[1][0]
    expect(prompt).toMatch(/^These are my recipes\.\n\nRework this recipe into prep and cook phases/)
    expect(prompt).toContain('"id": "kip-shoarma"')
  })

  it("replaces the recipe with a paste, and refuses another recipe's JSON", async () => {
    let check: PasteCheck = { ok: true, problems: [], recipes: [{ id: 'dal', title: 'Dal', result: 'new', changes: [] }] }
    const { fetchMock } = setup({
      'POST /api/recipes/check': () => check,
      [`PUT ${PATH}`]: { result: 'replaced', ...detail() },
    })
    await menu(/Paste JSON/)
    const dialog = screen.getByRole('dialog', { name: 'Paste JSON' })
    vi.useFakeTimers({ shouldAdvanceTime: true })

    fireEvent.change(within(dialog).getByRole('textbox'), { target: { value: '{"id": "dal"}' } })
    await act(async () => vi.advanceTimersByTime(CHECK_DELAY_MS))
    expect(await within(dialog).findByText('Not this recipe')).toBeInTheDocument()
    expect(within(dialog).getByRole('button', { name: 'Save' })).toBeDisabled()

    check = { ok: true, problems: [], recipes: [{ id: 'kip-shoarma', title: 'Kip', result: 'replace', changes: [{ kind: 'changed', text: 'Servings: 4 instead of 2' }] }] }
    fireEvent.change(within(dialog).getByRole('textbox'), { target: { value: '{"recipes": [{"id": "kip-shoarma"}]}' } })
    await act(async () => vi.advanceTimersByTime(CHECK_DELAY_MS))
    vi.useRealTimers()
    fireEvent.click(await within(dialog).findByRole('button', { name: 'Replace recipe' }))

    expect(await screen.findByText('Replaced. Undo is in the menu.')).toBeInTheDocument()
    expect(sentBody(fetchMock, 'PUT', PATH)).toEqual({ id: 'kip-shoarma' })
    await waitFor(() => expect(calls(fetchMock, PATH)).toBe(2))
  })

  it('undoes the last paste', async () => {
    const { fetchMock } = setup({
      [PATH]: detail({ previous_at: new Date(Date.now() - 5 * 60e3).toISOString() }),
      [`POST ${PATH}/undo`]: detail(),
    })

    await menu(/Undo last paste.*Pasted 5 min ago/)
    expect(await screen.findByText('Back to the version before the last paste.')).toBeInTheDocument()
    expect(calls(fetchMock, `${PATH}/undo`, 'POST')).toBe(1)
  })

  it('has no undo when nothing was pasted', async () => {
    setup()

    fireEvent.click(await screen.findByRole('button', { name: 'Recipe actions' }))
    expect(within(screen.getByRole('menu')).queryByRole('menuitem', { name: /Undo/ })).toBeNull()
  })

  it('deletes only after a second yes, and says so on the list', async () => {
    const { fetchMock } = setup({ [`DELETE ${PATH}`]: { deleted: 'kip-shoarma' } })

    await menu(/Delete recipe/)
    const ask = screen.getByRole('alert')
    fireEvent.click(within(ask).getByRole('button', { name: 'Keep it' }))
    expect(screen.queryByRole('alert')).toBeNull()

    await menu(/Delete recipe/)
    fireEvent.click(within(screen.getByRole('alert')).getByRole('button', { name: 'Delete for good' }))
    expect(await screen.findByText('Deleted "Kip shoarma uit de oven".')).toBeInTheDocument()
    expect(screen.getByRole('heading', { level: 1, name: 'Recipes' })).toBeInTheDocument()
    expect(fetchMock.mock.calls.some(([p, init]) => p === PATH && init?.method === 'DELETE')).toBe(true)
  })

  it('sends a new photo, resized, as JSON', async () => {
    const { fetchMock } = setup({ [`PUT ${PATH}/photo`]: detail() })
    await screen.findByRole('heading', { level: 1 })

    const input = screen.getByLabelText('Photo') as HTMLInputElement
    fireEvent.change(input, { target: { files: [new File(['x'], 'pan.jpg', { type: 'image/jpeg' })] } })
    expect(await screen.findByText('The photo is in.')).toBeInTheDocument()
    expect(sentBody(fetchMock, 'PUT', `${PATH}/photo`)).toEqual({ data: 'data:image/jpeg;base64,AAAA' })
  })
})
