import { act, fireEvent, screen, waitFor, within } from '@testing-library/react'
import { vi } from 'vitest'
import { CHECK_DELAY_MS } from '../components/recipes/PasteDialog'
import { RECIPES } from '../test/recipeFixtures'
import { renderRoute } from '../test/renderRoute'
import { failWith, sentBody, stubApi } from '../test/stubApi'

function setup(over: Record<string, unknown> = {}) {
  const fetchMock = stubApi({ '/api/recipes': RECIPES, ...over })
  return { fetchMock, ...renderRoute('/recipes') }
}

const cards = () => within(screen.getByRole('list', { name: 'Recipes' })).getAllByRole('link')

async function paste(text: string) {
  vi.useFakeTimers({ shouldAdvanceTime: true })
  fireEvent.click(await screen.findByRole('button', { name: 'Paste JSON' }))
  fireEvent.change(screen.getByRole('textbox'), { target: { value: text } })
  await act(async () => vi.advanceTimersByTime(CHECK_DELAY_MS))
  vi.useRealTimers()
}

describe('RecipesPage', () => {
  it('lists every recipe with its times, tags and photo', async () => {
    setup()

    expect(await screen.findByText('3 recipes · 1 to review')).toBeInTheDocument()
    const [creme, kip, dal] = cards()
    expect(creme).toHaveAttribute('href', '/recipes/cr%C3%A8me-brulee')
    expect(creme).toHaveTextContent('20 min prep4 h 20 min cook')
    expect(creme.querySelector('img')?.getAttribute('src')).toMatch(/^\/api\/recipes\/cr%C3%A8me-brulee\/photo\/thumb\?v=/)
    expect(kip).toHaveTextContent('#oven#kip')
    // Without a photo, the first letter on a tile; without a cook time, only prep.
    expect(dal.querySelector('img')).toBeNull()
    expect(dal).toHaveTextContent('D')
    expect(dal).toHaveTextContent('15 min prep')
    expect(dal).not.toHaveTextContent('cook')
    expect(within(dal).getByText('Needs review')).toBeInTheDocument()
  })

  it('searches titles and filters by tag or review', async () => {
    setup()
    await screen.findByText('3 recipes · 1 to review')
    const filters = screen.getByRole('group', { name: 'Filter' })

    fireEvent.change(screen.getByRole('searchbox', { name: 'Search recipes' }), { target: { value: 'creme' } })
    expect(cards()).toHaveLength(1)
    fireEvent.click(within(filters).getByRole('button', { name: 'kip' }))
    expect(screen.getByText('No recipes match.')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Show all recipes' }))
    expect(cards()).toHaveLength(3)

    fireEvent.click(within(filters).getByRole('button', { name: /Needs review 1/ }))
    expect(cards().map((c) => c.textContent)).toEqual([expect.stringContaining('Dal met spinazie')])
    expect(within(filters).getByRole('button', { name: /Needs review/ })).toHaveAttribute('aria-pressed', 'true')
  })

  it('invites a first paste when there are no recipes', async () => {
    setup({ '/api/recipes': { ...RECIPES, count: 0, review_count: 0, tags: [], recipes: [] } })

    expect(await screen.findByText('No recipes yet')).toBeInTheDocument()
    expect(screen.queryByRole('searchbox')).toBeNull()
  })

  it('says so when the hub does not answer, and tries again', async () => {
    const { fetchMock } = setup({ '/api/recipes': failWith(503, { detail: 'down' }) })

    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent('Recipes are not available right now')
    fireEvent.click(within(alert).getByRole('button', { name: 'Try again' }))
    await waitFor(() => expect(fetchMock.mock.calls.filter(([p]) => p === '/api/recipes')).toHaveLength(2))
  })

  it('shows what is wrong with a paste and saves nothing', async () => {
    const check = { ok: false, problems: [{ path: 'servings', message: 'is text; it should be a number, like 2' }], recipes: [] }
    const { fetchMock } = setup({ 'POST /api/recipes/check': check })

    await paste('{ "servings": ')
    expect(await screen.findByText('Not valid JSON')).toBeInTheDocument()

    await paste('{"servings": "2"}')
    const problems = await screen.findByText('1 thing to fix')
    expect(problems.parentElement).toHaveTextContent('servingsis text; it should be a number, like 2')
    expect(sentBody(fetchMock, 'POST', '/api/recipes/check')).toEqual({ data: { servings: '2' } })
    expect(screen.getByRole('button', { name: 'Save' })).toBeDisabled()
  })

  it('shows what a paste replaces, then saves it and reloads the list', async () => {
    const check = {
      ok: true,
      problems: [],
      recipes: [{ id: 'kip-shoarma-uit-de-oven', title: 'Kip shoarma uit de oven', result: 'replace', changes: [
        { kind: 'changed', text: 'kaneel: ¼ tl instead of ½ tl' },
        { kind: 'added', text: 'New prep phase "Knoflooksaus", 1 step' },
      ] }],
    }
    const { fetchMock } = setup({
      'POST /api/recipes/check': check,
      'POST /api/recipes/import': { saved: [{ id: 'kip-shoarma-uit-de-oven', title: 'Kip', result: 'replaced' }] },
    })

    await paste('{"id": "kip-shoarma-uit-de-oven"}')
    const summary = await screen.findByRole('list', { name: 'What this does' })
    expect(summary).toHaveTextContent('Replaces "Kip shoarma uit de oven"')
    expect(summary).toHaveTextContent('~kaneel: ¼ tl instead of ½ tl')
    expect(summary).toHaveTextContent('The photo stays.')

    fireEvent.click(screen.getByRole('button', { name: 'Replace recipe' }))
    expect(await screen.findByText('Replaced 1 recipe.')).toBeInTheDocument()
    expect(sentBody(fetchMock, 'POST', '/api/recipes/import')).toEqual({ data: { id: 'kip-shoarma-uit-de-oven' }, replace: true })
    await waitFor(() => expect(fetchMock.mock.calls.filter(([p]) => p === '/api/recipes')).toHaveLength(2))
  })

  it('copies every recipe and the format for Claude', async () => {
    const writeText = vi.fn(() => Promise.resolve())
    vi.stubGlobal('navigator', { ...navigator, clipboard: { writeText } })
    const exported = { schema: 'hub-recipe/1', guide: 'These are my recipes', json_schema: {}, recipes: [{ id: 'a' }, { id: 'b' }] }
    setup({ '/api/recipes/export': exported })

    fireEvent.click(await screen.findByRole('button', { name: 'Copy all' }))
    expect(await screen.findByText(/Copied 2 recipes and the format \(1 kB\)/)).toBeInTheDocument()
    expect(writeText).toHaveBeenCalledWith(JSON.stringify(exported))
  })

  it('keeps Paste JSON and Copy all in a menu on the phone', async () => {
    setup()

    const menuButton = await screen.findByRole('button', { name: 'Recipe actions' })
    fireEvent.click(menuButton)
    expect(menuButton).toHaveAttribute('aria-expanded', 'true')
    fireEvent.click(within(screen.getByRole('menu')).getByRole('menuitem', { name: /Paste JSON/ }))
    expect(screen.queryByRole('menu')).toBeNull()
    expect(screen.getByRole('dialog', { name: 'Paste JSON' })).toBeInTheDocument()
  })
})
