import { fireEvent, screen, within } from '@testing-library/react'
import type { Headline, HeadlinesResponse } from '../../lib/newsTypes'
import { ARTICLES, NEWS_GROUPS } from '../../test/newsFixtures'
import { renderRoute } from '../../test/renderRoute'
import { failWith, sentBody, stubApi } from '../../test/stubApi'

const minutesAgo = (n: number) => new Date(Date.now() - n * 60_000).toISOString()

const story = (id: string, over: Partial<Headline> = {}): Headline => ({
  id,
  group_id: 'nl',
  group: 'Nederland',
  title: `Story ${id}`,
  source: 'NOS',
  url: `https://news.example/${id}`,
  published: minutesAgo(12),
  summary: `About ${id}`,
  image: 'lead',
  ...over,
})

const HEADLINES: HeadlinesResponse = {
  as_of: minutesAgo(1),
  stale: false,
  items: [
    story('h1', { title: 'Kabinet presenteert plannen' }),
    story('h2', { group_id: 'home', group: 'Self-hosted', source: 'Tweakers', image: null, published: minutesAgo(40) }),
    story('h3', { group_id: 'tech', group: 'Tech', source: 'The Verge', image: 'thumb', published: minutesAgo(60) }),
  ],
}

function setup(over: Record<string, unknown> = {}, path = '/news') {
  const fetchMock = stubApi({
    '/api/news/groups': NEWS_GROUPS,
    '/api/news/articles?limit=50&offset=0': { articles: ARTICLES, total: ARTICLES.length },
    '/api/news/headlines': HEADLINES,
    ...over,
  })
  return { fetchMock, ...renderRoute(path) }
}

const block = () => screen.findByRole('region', { name: 'Headlines' })

describe('Headlines', () => {
  it('shows the lead over its picture and the others with thumbnails or a letter tile', async () => {
    setup()

    const headlines = await block()
    expect(within(headlines).getByText('Nederland · Self-hosted · Tech')).toBeInTheDocument()
    const items = within(headlines).getAllByRole('listitem')
    expect(items.map((i) => i.getAttribute('data-image'))).toEqual(['lead', 'none', 'thumb'])
    expect(within(items[0]).getByRole('heading', { name: 'Kabinet presenteert plannen' })).toBeInTheDocument()
    expect(items[0].querySelector('img')).toHaveAttribute('src', '/api/news/headlines/h1/image/lead')
    expect(within(items[0]).getByText('About h1')).toBeInTheDocument()
    expect(within(items[0]).getByText('12 min ago')).toBeInTheDocument()
    expect(items[1].querySelector('img')).toBeNull()
    expect(within(items[1]).getByText('T')).toBeInTheDocument()
    expect(items[2].querySelector('img')).toHaveAttribute('src', '/api/news/headlines/h3/image/thumb')
    expect(within(items[1]).getByRole('link')).toHaveAttribute('href', '/news?a=h2')
  })

  it('saves a story to Readeck and fills its bookmark', async () => {
    const { fetchMock } = setup({ 'POST /api/save': { saved: true, bookmark_id: 'x' } })

    fireEvent.click(within(await block()).getByRole('button', { name: 'Save to Readeck: Story h2' }))

    expect(await screen.findByRole('button', { name: 'Saved to Readeck: Story h2' })).toBeDisabled()
    expect(sentBody(fetchMock, 'POST', '/api/save')).toEqual({ url: 'https://news.example/h2', title: 'Story h2' })
    expect(screen.getByRole('button', { name: 'Save to Readeck: Kabinet presenteert plannen' })).toBeEnabled()
  })

  it('says why saving failed and lets you try again', async () => {
    setup({ 'POST /api/save': failWith(502, { detail: 'Readeck is not reachable' }) })

    fireEvent.click(within(await block()).getByRole('button', { name: 'Save to Readeck: Story h3' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('Readeck is not reachable')
    expect(screen.getByRole('button', { name: 'Saving failed, try again: Story h3' })).toBeEnabled()
  })

  it('notes a stale answer and stays away without one', async () => {
    setup({ '/api/news/headlines': { ...HEADLINES, stale: true } })
    expect(await screen.findByText('Showing the last known figures.')).toBeInTheDocument()
  })

  it('is not there before the first headlines are in', async () => {
    setup({ '/api/news/headlines': failWith(503, {}) })

    expect(await screen.findByText('2 unread')).toBeInTheDocument()
    expect(screen.queryByRole('region', { name: 'Headlines' })).not.toBeInTheDocument()
  })

  it('hides with the list on a phone while an article is open', async () => {
    setup({}, '/news?a=a1')

    expect((await block()).parentElement).toHaveClass('hidden', 'lg:block')
  })
})
