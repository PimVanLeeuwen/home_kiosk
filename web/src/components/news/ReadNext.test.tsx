import { fireEvent, screen, within } from '@testing-library/react'
import { vi } from 'vitest'
import type { HeadlinesResponse } from '../../lib/newsTypes'
import { goOnWith, minutesLeft } from '../../lib/readNext'
import { ARTICLES, BOOKMARKS, NEWS_GROUPS } from '../../test/newsFixtures'
import { renderRoute } from '../../test/renderRoute'
import { stubApi } from '../../test/stubApi'

// The top stories are articles: a3 is read in the list, a1 is not.
const HEADLINES: HeadlinesResponse = {
  as_of: new Date().toISOString(),
  stale: false,
  items: [
    { id: 'a3', group_id: 'tech', group: 'Tech', title: 'Old story', source: 'Ars', url: 'https://x/a3', published: ARTICLES[2].published, summary: null, image: null },
    { id: 'a1', group_id: 'nl', group: 'Nederland', title: 'Kabinet presenteert Miljoenennota', source: 'NOS', url: 'https://x/a1', published: ARTICLES[0].published, summary: null, image: 'lead', sources: [{ id: 'x', source: 'NU.nl', url: 'https://x/x' }] },
  ],
}

function setup(path: string, over: Record<string, unknown> = {}) {
  const fetchMock = stubApi({
    '/api/news/groups': [...NEWS_GROUPS].reverse().map((g) => (g.id === 'tech' ? { ...g, unread: 7 } : g)),
    '/api/news/articles?limit=50&offset=0': { articles: ARTICLES, total: ARTICLES.length },
    '/api/news/articles?group=tech&unread=true&limit=50&offset=0': { articles: [ARTICLES[1]], total: 1 },
    '/api/news/headlines': HEADLINES,
    '/api/saved?archived=false&limit=30&offset=0': { bookmarks: BOOKMARKS, total: 2 },
    ...over,
  })
  return { fetchMock, ...renderRoute(path) }
}

describe('ReadNext', () => {
  it('on News: the top story not yet read, the saved one half read, and the busiest group', async () => {
    const { fetchMock } = setup('/news')

    const pane = screen.getByRole('region', { name: 'Reader' })
    expect(await within(pane).findByText('Read next')).toBeInTheDocument()
    const top = await within(pane).findByRole('link', { name: /Kabinet presenteert Miljoenennota/ })
    expect(top).toHaveAttribute('href', '/news?a=a1')
    expect(top).toHaveTextContent('Top story · Nederland · 2 feeds')
    const saved = await within(pane).findByRole('link', { name: /Saved: Why trains run late/ })
    expect(saved).toHaveAttribute('href', '/saved?b=b1')
    expect(saved).toHaveTextContent('Blog · 4 min left')

    fireEvent.click(await within(pane).findByRole('button', { name: /Tech: 7 unread/ }))
    await vi.waitFor(() =>
      expect(fetchMock.mock.calls.map(([url]) => String(url))).toContain('/api/news/articles?group=tech&unread=true&limit=50&offset=0'),
    )
  })

  it('on Saved: the busiest group opens News on its unread articles', async () => {
    setup('/saved')

    const pane = screen.getByRole('region', { name: 'Reader' })
    expect(await within(pane).findByRole('link', { name: /Tech: 7 unread/ })).toHaveAttribute('href', '/news?group=tech')
    // Nothing is read on Saved's side: the first top story leads.
    expect(await within(pane).findByRole('link', { name: /Old story/ })).toHaveAttribute('href', '/news?a=a3')
  })

  it('News opens on a group from the address', async () => {
    setup('/news?group=tech')

    const filter = screen.getByRole('group', { name: 'Filter' })
    expect(await within(filter).findByRole('button', { name: /Tech/ })).toHaveAttribute('aria-pressed', 'true')
    expect(within(filter).getByRole('button', { name: 'Unread' })).toHaveAttribute('aria-pressed', 'true')
  })

  it('says to pick an article when there is nothing to suggest', async () => {
    setup('/news', { '/api/news/groups': [], '/api/news/headlines': { ...HEADLINES, items: [] }, '/api/saved?archived=false&limit=30&offset=0': { bookmarks: [], total: 0 } })

    expect(await screen.findByText('Pick an article to read it here.')).toBeInTheDocument()
  })
})

describe('what to read next', () => {
  it('goes on with the newest half-read bookmark, else the newest not started', () => {
    const [half, unreadable] = BOOKMARKS
    const fresh = { ...half, id: 'b3', progress: 0 }
    expect(goOnWith([fresh, half, unreadable])?.id).toBe('b1')
    expect(goOnWith([unreadable, fresh])?.id).toBe('b3')
    // One read 96% through is as good as done.
    expect(goOnWith([{ ...half, progress: 96 }, fresh])?.id).toBe('b3')
    expect(minutesLeft(half)).toBe('4 min left')
    expect(minutesLeft(fresh)).toBe('6 min read')
    expect(minutesLeft({ ...half, reading_minutes: null })).toBeNull()
  })
})
