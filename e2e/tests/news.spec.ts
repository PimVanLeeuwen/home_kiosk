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

  await expect(page.getByText('1 unread')).toBeVisible()
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
  await page.getByRole('link', { name: /Why trains run late/ }).click()
  const reader = page.getByRole('article', { name: 'Why trains run late' })
  await expect(reader.getByRole('button', { name: 'Archive' })).toBeVisible()
  await expect(reader.getByText('Library scans now take half the time')).toBeVisible()
})
