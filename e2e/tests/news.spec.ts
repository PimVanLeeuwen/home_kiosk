import { expect, test, type Page } from '@playwright/test'

const now = () => new Date().toISOString()
const ARTICLE = {
  id: 'a1',
  url: 'https://news.example/a1',
  title: 'Jellyfin 12.1 lands with faster library scans',
  source: 'Jellyfin blog',
  group_id: 'self',
  published: now(),
  read: false,
}
const CONTENT = {
  ok: true, reason: null, title: ARTICLE.title, author: null, date: null, site: 'Jellyfin blog',
  blocks: [
    { type: 'paragraph', text: 'Library scans now take half the time on large collections.', items: [], src: '' },
    { type: 'heading', text: 'Tone mapping', items: [], src: '' },
    { type: 'paragraph', text: 'HDR content tone maps correctly on Intel hardware again.', items: [], src: '' },
  ],
}

async function stubNews(page: Page) {
  const read: unknown[] = []
  await page.route('**/api/news/groups', (r) => r.fulfill({ json: [{ id: 'self', title: 'Self-hosted', unread: 1 }] }))
  await page.route('**/api/news/articles?**', (r) => r.fulfill({ json: { articles: [ARTICLE], total: 1 } }))
  await page.route('**/api/news/articles/a1', (r) => r.fulfill({ json: ARTICLE }))
  await page.route('**/api/news/articles/a1/content', (r) => r.fulfill({ json: CONTENT }))
  await page.route('**/api/news/articles/a1/read', (r) => {
    read.push(r.request().postDataJSON())
    return r.fulfill({ json: { read: true } })
  })
  return read
}

test('News opens an article in the reader and marks it read', async ({ page, isMobile }) => {
  const read = await stubNews(page)
  await page.goto('/news')

  await expect(page.getByText('1 unread', { exact: true })).toBeVisible()
  await page.getByRole('link', { name: /Jellyfin 12.1 lands/ }).click()

  const reader = page.getByRole('article', { name: ARTICLE.title })
  await expect(reader.getByRole('heading', { name: 'Tone mapping' })).toBeVisible()
  await expect.poll(() => read).toEqual([{ read: true }])
  await expect(page).toHaveURL('/news?a=a1')

  if (isMobile) {
    // The phone shows the reader alone, with a way back.
    await expect(page.getByRole('searchbox', { name: 'Search articles' })).toBeHidden()
    await reader.getByRole('link', { name: 'News' }).click()
    await expect(page).toHaveURL('/news')
    await expect(page.getByRole('searchbox', { name: 'Search articles' })).toBeVisible()
  } else {
    // The laptop keeps the list beside it.
    await expect(page.getByRole('searchbox', { name: 'Search articles' })).toBeVisible()
  }
})

test('Saved lists Readeck bookmarks and reads one', async ({ page }) => {
  await page.route('**/api/saved?**', (r) => r.fulfill({ json: { total: 1, bookmarks: [{
    id: 'b1', url: 'https://blog.example/trains', title: 'Why trains run late', site: 'Blog', created: now(),
    published: null, description: null, reading_minutes: 6, progress: 0, archived: false, readable: true, thumbnail: false,
  }] } }))
  await page.route('**/api/saved/b1/content', (r) => r.fulfill({ json: { ...CONTENT, title: 'Why trains run late' } }))
  await page.goto('/saved')

  await expect(page.getByText('1 in Readeck')).toBeVisible()
  await page.getByRole('region', { name: 'Bookmarks' }).getByRole('link', { name: /Why trains run late/ }).click()
  const reader = page.getByRole('article', { name: 'Why trains run late' })
  await expect(reader.getByRole('button', { name: 'Archive' })).toBeVisible()
  await expect(reader.getByText('Library scans now take half the time')).toBeVisible()
})

test('News opens with the headlines: one story per group, saved to Readeck from the bookmark', async ({ page }) => {
  await stubNews(page)
  const saved: unknown[] = []
  const minutesAgo = (n: number) => new Date(Date.now() - n * 60_000).toISOString()
  const story = (id: string, over: Record<string, unknown>) => ({
    id, group_id: 'self', group: 'Self-hosted', title: `Story ${id}`, source: 'NOS', url: `https://news.example/${id}`,
    published: minutesAgo(12), summary: null, image: null, ...over,
  })
  await page.route('**/api/news/headlines', (r) => r.fulfill({ json: { as_of: now(), stale: false, items: [
    story('h1', { title: 'Kabinet presenteert plannen', group: 'Nederland', image: 'lead', summary: 'Het kabinet wil sneller bouwen.' }),
    story('a1', { title: ARTICLE.title, source: 'Jellyfin blog', published: minutesAgo(40) }),
    story('h3', { group: 'Tech', source: 'The Verge', image: 'thumb', published: minutesAgo(60) }),
  ] } }))
  const pictures: string[] = []
  await page.route('**/api/news/headlines/*/image/*', (r) => {
    pictures.push(new URL(r.request().url()).pathname)
    return r.fulfill({ status: 404 })
  })
  await page.route('**/api/save', (r) => {
    saved.push(r.request().postDataJSON())
    return r.fulfill({ json: { saved: true, bookmark_id: 'b1' } })
  })
  await page.goto('/news')

  const headlines = page.getByRole('region', { name: 'Headlines' })
  await expect(headlines.getByRole('heading', { name: 'Kabinet presenteert plannen' })).toBeVisible()
  // Which pictures, not how often: the reading pane's "read next" shows the lead's picture too,
  // and a 404 is not cached, so it may be asked for twice.
  await expect.poll(() => [...new Set(pictures)].sort()).toEqual(['/api/news/headlines/h1/image/lead', '/api/news/headlines/h3/image/thumb'])

  await headlines.getByRole('button', { name: 'Save to Readeck: Story h3' }).click()
  await expect(headlines.getByRole('button', { name: 'Saved to Readeck: Story h3' })).toBeDisabled()
  expect(saved).toEqual([{ url: 'https://news.example/h3', title: 'Story h3' }])

  await headlines.getByRole('link', { name: /Jellyfin 12.1 lands/ }).click()
  await expect(page).toHaveURL('/news?a=a1')
  await expect(page.getByRole('article', { name: ARTICLE.title }).getByRole('heading', { name: 'Tone mapping' })).toBeVisible()
})

test('News leads with the top stories when Claude groups them', async ({ page }) => {
  const at = new Date().toISOString()
  const item = (id: string, source: string, extra = {}) => ({
    id, group_id: 'nl', group: 'Nederland', title: `Story ${id}`, source, url: `https://news.example/${id}`,
    published: at, summary: null, image: null, ...extra,
  })
  await page.route('**/api/news/headlines', (route) => route.fulfill({ json: {
    as_of: at, stale: false, grouped: true, items: [
      item('a', 'NOS', { story: 'The cabinet presents a housing plan.', sources: [{ id: 'b', source: 'NU.nl', url: 'https://nu.example/b' }] }),
      item('c', 'Tweakers'),
    ],
  } }))
  await page.goto('/news')

  const top = page.getByRole('region', { name: 'Top stories' })
  await expect(top).toContainText('The cabinet presents a housing plan.')
  await expect(top.getByRole('link', { name: 'NU.nl' })).toHaveAttribute('href', '/news?a=b')
})

test('Before an article is picked, the reader suggests what to read next', async ({ page, isMobile }) => {
  test.skip(isMobile, 'the reading pane shows beside the list on a wide screen only')
  await stubNews(page)
  await page.route('**/api/news/headlines', (r) => r.fulfill({ json: { as_of: now(), stale: false, items: [
    { id: 'a1', group_id: 'self', group: 'Self-hosted', title: ARTICLE.title, source: 'Jellyfin blog', url: ARTICLE.url,
      published: now(), summary: null, image: null }] } }))
  await page.route('**/api/saved?**', (r) => r.fulfill({ json: { total: 1, bookmarks: [{
    id: 'b1', url: 'https://blog.example/trains', title: 'Why trains run late', site: 'Blog', created: now(), published: null,
    description: null, reading_minutes: 10, progress: 30, archived: false, readable: true, thumbnail: false }] } }))
  await page.route('**/api/saved/b1/content', (r) => r.fulfill({ json: { ...CONTENT, title: 'Why trains run late' } }))
  await page.goto('/news')

  const pane = page.getByRole('region', { name: 'Reader' })
  await expect(pane.getByText('Read next')).toBeVisible()
  await expect(pane.getByRole('link', { name: /Top story · Self-hosted/ })).toBeVisible()
  await pane.getByRole('link', { name: /Saved: Why trains run late/ }).click()
  await expect(page).toHaveURL(/\/saved\?b=b1$/)
  await expect(page.getByRole('heading', { name: 'Why trains run late' })).toBeVisible()
})
