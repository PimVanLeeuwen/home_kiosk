import type { Article, ArticleContent, Bookmark, FeedGroup, NewsGroup } from '../lib/newsTypes'

export const NEWS_GROUPS: NewsGroup[] = [
  { id: 'nl', title: 'Nederland', unread: 1 },
  { id: 'tech', title: 'Tech', unread: 1 },
]

const article = (id: string, title: string, over: Partial<Article> = {}): Article => ({
  id,
  url: `https://news.example/${id}`,
  title,
  source: 'NOS',
  group_id: 'nl',
  published: '2026-09-30T17:48:00Z',
  read: false,
  ...over,
})

export const ARTICLES: Article[] = [
  article('a1', 'Kabinet presenteert Miljoenennota'),
  article('a2', 'Jellyfin 12.1 lands', { source: 'Hacker News', group_id: 'tech', published: '2026-09-30T17:00:00Z' }),
  article('a3', 'Old story', { source: 'Ars', group_id: 'tech', published: '2026-09-28T08:00:00Z', read: true }),
]

const block = (type: ArticleContent['blocks'][number]['type'], text = '', extra = {}) => ({
  type,
  text,
  items: [],
  src: '',
  ...extra,
})

export const CONTENT: ArticleContent = {
  ok: true,
  reason: null,
  title: 'Kabinet presenteert Miljoenennota met lastenverlichting',
  author: 'Redactie',
  date: '2026-09-30',
  site: 'NOS',
  blocks: [
    block('paragraph', 'Het kabinet verlaagt de belasting voor middeninkomens.'),
    block('heading', 'Wat verandert er'),
    block('image', 'Prinsjesdag', { src: '/api/news/articles/a1/images/0' }),
    block('quote', 'Dit is een begroting voor iedereen.'),
    block('list', '', { items: ['Lagere inkomstenbelasting', 'Hogere zorgtoeslag'] }),
  ],
}

export const UNREADABLE: ArticleContent = {
  ok: false,
  reason: 'No readable text (paywall or app-only page)',
  title: null,
  author: null,
  date: null,
  site: null,
  blocks: [],
}

export const BOOKMARKS: Bookmark[] = [
  {
    id: 'b1',
    url: 'https://blog.example/trains',
    title: 'Why trains run late',
    site: 'Blog',
    created: '2026-09-29T10:00:00Z',
    published: null,
    description: null,
    reading_minutes: 6,
    progress: 40,
    archived: false,
    readable: true,
    thumbnail: true,
  },
  {
    id: 'b2',
    url: 'https://app.example/x',
    title: 'An app-only page',
    site: 'App',
    created: '2026-09-28T10:00:00Z',
    published: null,
    description: null,
    reading_minutes: null,
    progress: 0,
    archived: false,
    readable: false,
    thumbnail: false,
  },
]

export const FEEDS: FeedGroup[] = [
  {
    id: 'nl',
    title: 'Nederland',
    feeds: [
      { id: 1, group_id: 'nl', url: 'https://feeds.nos.nl/nosnieuwsalgemeen', name: 'NOS', checked_at: '2026-09-30T17:50:00Z', item_count: 20, error: null },
      { id: 2, group_id: 'nl', url: 'https://dead.example/rss', name: null, checked_at: '2026-09-30T17:50:00Z', item_count: 0, error: 'HTTP 404' },
    ],
  },
  { id: 'tech', title: 'Tech', feeds: [] },
]
