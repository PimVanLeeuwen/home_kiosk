import { fireEvent, screen, waitFor, within } from '@testing-library/react'
import { ARTICLES, CONTENT, NEWS_GROUPS, UNREADABLE } from '../test/newsFixtures'
import { renderRoute } from '../test/renderRoute'
import { failWith, sentBody, stubApi } from '../test/stubApi'

const LIST = { articles: ARTICLES, total: ARTICLES.length }

function setup(over: Record<string, unknown> = {}, path = '/news') {
  const fetchMock = stubApi({
    '/api/news/groups': NEWS_GROUPS,
    '/api/news/articles?limit=50&offset=0': LIST,
    '/api/news/articles/a1': ARTICLES[0],
    '/api/news/articles/a1/content': CONTENT,
    'POST /api/news/articles/a1/read': (body: unknown) => body,
    ...over,
  })
  return { fetchMock, ...renderRoute(path) }
}

describe('NewsPage', () => {
  it('lists articles by day with unread counts per group', async () => {
    setup()

    expect(await screen.findByText('2 unread')).toBeInTheDocument()
    const list = screen.getByRole('region', { name: 'Articles' })
    const links = await within(list).findAllByRole('link')
    expect(links.map((l) => l.textContent)).toEqual([
      expect.stringContaining('Kabinet presenteert Miljoenennota'),
      expect.stringContaining('Jellyfin 12.1 lands'),
      expect.stringContaining('Old story'),
    ])
    expect(links[0]).toHaveTextContent('unread')
    expect(links[2]).not.toHaveTextContent('unread')
    expect(within(list).getByRole('button', { name: /Tech\s*1/ })).toBeInTheDocument()
    // A group chip in the group's colour, the same as on Home; unread dots glow.
    expect(within(links[1]).getByText('Tech')).toHaveStyle({ color: '#8cc4ff' })
    expect(links[0].querySelector('[aria-hidden="true"]')).toHaveClass('bg-accent-line')
    expect(links[2].querySelector('[aria-hidden="true"]')).not.toHaveClass('bg-accent-line')
    expect(within(list).getByRole('button', { name: /Tech\s*1/ }).querySelector('i')).toHaveStyle({ backgroundColor: '#8cc4ff' })
  })

  it('filters by group, unread and search', async () => {
    const { fetchMock } = setup({
      '/api/news/articles?group=tech&limit=50&offset=0': { articles: ARTICLES.slice(1), total: 2 },
      '/api/news/articles?group=tech&unread=true&limit=50&offset=0': { articles: ARTICLES.slice(1, 2), total: 1 },
      '/api/news/articles?group=tech&unread=true&q=jelly&limit=50&offset=0': { articles: [], total: 0 },
    })

    fireEvent.click(await screen.findByRole('button', { name: /Tech/ }))
    await waitFor(() => expect(screen.queryByText('Kabinet presenteert Miljoenennota')).not.toBeInTheDocument())
    fireEvent.click(screen.getByRole('button', { name: 'Unread' }))
    await waitFor(() => expect(screen.queryByText('Old story')).not.toBeInTheDocument())
    fireEvent.change(screen.getByRole('searchbox', { name: 'Search articles' }), { target: { value: 'jelly' } })
    expect(await screen.findByText('Nothing matches “jelly”.')).toBeInTheDocument()
    expect(fetchMock).toHaveBeenCalledWith('/api/news/articles?group=tech&unread=true&q=jelly&limit=50&offset=0', expect.anything())
  })

  it('reads an article as text blocks and marks it read', async () => {
    const { fetchMock } = setup({}, '/news?a=a1')

    const reader = await screen.findByRole('article', { name: CONTENT.title! })
    expect(within(reader).getByText('Het kabinet verlaagt de belasting voor middeninkomens.')).toBeInTheDocument()
    expect(within(reader).getByRole('heading', { name: 'Wat verandert er' })).toBeInTheDocument()
    expect(within(reader).getByRole('img', { name: 'Prinsjesdag' })).toHaveAttribute('src', '/api/news/articles/a1/images/0')
    expect(within(reader).getByText('Dit is een begroting voor iedereen.').tagName).toBe('BLOCKQUOTE')
    expect(within(reader).getAllByRole('listitem')).toHaveLength(2)
    expect(within(reader).getByRole('link', { name: 'Open original (opens in a new tab)' })).toHaveAttribute(
      'href',
      'https://news.example/a1',
    )
    await waitFor(() => expect(sentBody(fetchMock, 'POST', '/api/news/articles/a1/read')).toEqual({ read: true }))
    // The list follows: the open article no longer shows as unread.
    const list = screen.getByRole('region', { name: 'Articles' })
    await waitFor(() => expect(within(list).getAllByRole('link')[0]).not.toHaveTextContent('unread'))
  })

  it('saves to Readeck and can mark the article unread again', async () => {
    const { fetchMock } = setup({ 'POST /api/save': { saved: true, bookmark_id: 'x' } }, '/news?a=a1')

    fireEvent.click(await screen.findByRole('button', { name: 'Save to Readeck' }))
    expect(await screen.findByRole('button', { name: 'Saved to Readeck' })).toBeDisabled()
    expect(sentBody(fetchMock, 'POST', '/api/save')).toEqual({ url: 'https://news.example/a1', title: ARTICLES[0].title })

    fireEvent.click(screen.getByRole('button', { name: 'Mark unread' }))
    expect(await screen.findByRole('button', { name: 'Mark read' })).toBeInTheDocument()
    expect(sentBody(fetchMock, 'POST', '/api/news/articles/a1/read', 1)).toEqual({ read: false })
  })

  it('shows why Saving to Readeck failed', async () => {
    setup({ 'POST /api/save': failWith(502, { detail: 'Readeck rejected the token' }) }, '/news?a=a1')

    fireEvent.click(await screen.findByRole('button', { name: 'Save to Readeck' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Readeck rejected the token')
  })

  it('offers the original when a page does not read well', async () => {
    setup({ '/api/news/articles/a1/content': UNREADABLE }, '/news?a=a1')

    expect(await screen.findByText('No readable text (paywall or app-only page)')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /Open the original/ })).toHaveAttribute('href', 'https://news.example/a1')
  })

  it('pages through long lists', async () => {
    setup({
      '/api/news/articles?limit=50&offset=0': { articles: ARTICLES.slice(0, 2), total: 3 },
      '/api/news/articles?limit=50&offset=2': { articles: ARTICLES.slice(2), total: 3 },
    })

    fireEvent.click(await screen.findByRole('button', { name: 'Show more (1 left)' }))
    expect(await screen.findByText('Old story')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Show more/ })).not.toBeInTheDocument()
  })

  it('shows a leading image as the hero, a reading-progress line and the group in its colour', async () => {
    setup(
      { '/api/news/articles/a1/content': { ...CONTENT, blocks: [CONTENT.blocks[2], ...CONTENT.blocks.filter((_, i) => i !== 2)] } },
      '/news?a=a1',
    )

    const reader = await screen.findByRole('article', { name: /Miljoenennota/ })
    const hero = await within(reader).findByRole('img', { name: 'Prinsjesdag' })
    // The hero stands above the text, not inside it.
    expect(hero.closest('figure')?.nextElementSibling?.textContent).toMatch(/^Het kabinet/)
    expect(within(reader).getByRole('progressbar', { name: 'Read' })).toHaveAttribute('aria-valuemax', '100')
    expect(within(reader).getByText('Nederland')).toHaveStyle({ color: '#b4aaff' })
  })

  it('leaves an image later in the article where it is', async () => {
    setup({}, '/news?a=a1')
    const reader = await screen.findByRole('article', { name: /Miljoenennota/ })
    const image = await within(reader).findByRole('img', { name: 'Prinsjesdag' })
    expect(image.closest('figure')?.previousElementSibling?.textContent).toBe('Wat verandert er')
  })

  it('marks everything read', async () => {
    const { fetchMock } = setup({ 'POST /api/news/read-all': { marked: 2 } })

    fireEvent.click(await screen.findByRole('button', { name: 'Mark all read' }))
    expect(sentBody(fetchMock, 'POST', '/api/news/read-all')).toEqual({ group: null })
  })
})
