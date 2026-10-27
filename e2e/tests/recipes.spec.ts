import { expect, test, type Page } from '@playwright/test'

// Made-up recipes; the photos are one grey pixel.
const PNG = Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==', 'base64')
const recipe = (id: string, title: string, tags: string[], over: Record<string, unknown> = {}) => ({
  id, title, tags, times: { prep_min: 20, cook_min: 30 }, servings: 2, needs_review: false,
  updated_at: '2026-10-27T18:00:00+00:00', photo: '2026-10-27T18:00:00+00:00', ...over,
})
const LIST = {
  as_of: '2026-10-27T18:00:00+00:00', stale: false, count: 3, review_count: 1,
  tags: [{ tag: 'oven', count: 2 }, { tag: 'vega', count: 1 }],
  recipes: [
    recipe('kip-shoarma', 'Kip shoarma uit de oven', ['oven']),
    recipe('aubergine', 'Geroosterde aubergine', ['oven', 'vega'], { times: { prep_min: 20, cook_min: 260 } }),
    recipe('bulgogi', 'Koreaanse bulgogi', [], { needs_review: true, photo: null }),
  ],
}

async function stub(page: Page) {
  await page.route('**/api/recipes', (r) => r.fulfill({ json: LIST }))
  await page.route('**/api/recipes/*/photo/*', (r) => r.fulfill({ body: PNG, contentType: 'image/png' }))
}

async function action(page: Page, isMobile: boolean, name: string) {
  if (isMobile) {
    await page.getByRole('button', { name: 'Recipe actions' }).click()
    await page.getByRole('menuitem', { name: new RegExp(name) }).click()
  } else {
    await page.getByRole('button', { name }).click()
  }
}

test('Recipes opens from the tab bar or the Kitchen group, and searches and filters', async ({ page, isMobile }) => {
  await stub(page)
  await page.goto('/')
  if (isMobile) await page.locator('nav.fixed').getByRole('link', { name: 'Recipes' }).click()
  else await page.locator('aside').getByRole('link', { name: 'Recipes' }).click()

  await expect(page).toHaveTitle('Recipes · Home hub')
  await expect(page.getByText('3 recipes · 1 to review')).toBeVisible()
  const list = page.getByRole('list', { name: 'Recipes' })
  await expect(list.getByRole('link')).toHaveCount(3)
  await expect(list.getByRole('link', { name: /Geroosterde aubergine/ })).toContainText('4 h 20 min cook')
  await expect(list.getByRole('link', { name: /Koreaanse bulgogi/ })).toContainText('Needs review')

  await page.getByRole('searchbox', { name: 'Search recipes' }).fill('kip')
  await expect(list.getByRole('link')).toHaveCount(1)
  await page.getByRole('searchbox', { name: 'Search recipes' }).fill('')
  await page.getByRole('group', { name: 'Filter' }).getByRole('button', { name: 'vega' }).click()
  await expect(list.getByRole('link')).toHaveText([/Geroosterde aubergine/])
})

test('Paste JSON shows what is wrong, then adds the recipe', async ({ page, isMobile }) => {
  await stub(page)
  let saved: unknown = null
  await page.route('**/api/recipes/check', (r) => {
    const { data } = r.request().postDataJSON() as { data: { servings: unknown } }
    r.fulfill({ json: typeof data.servings === 'number'
      ? { ok: true, problems: [], recipes: [{ id: 'dal', title: 'Dal met spinazie', result: 'new', changes: [] }] }
      : { ok: false, problems: [{ path: 'servings', message: 'is text; it should be a number, like 2' }], recipes: [] } })
  })
  await page.route('**/api/recipes/import', (r) => {
    saved = r.request().postDataJSON()
    r.fulfill({ json: { saved: [{ id: 'dal', title: 'Dal met spinazie', result: 'added' }] } })
  })
  await page.goto('/recipes')

  await action(page, isMobile, 'Paste JSON')
  const dialog = page.getByRole('dialog', { name: 'Paste JSON' })
  await dialog.getByRole('textbox').fill('{"id": "dal", "servings": "2"}')
  await expect(dialog.getByRole('alert')).toContainText('servingsis text; it should be a number, like 2')
  await expect(dialog.getByRole('button', { name: 'Save' })).toBeDisabled()

  await dialog.getByRole('textbox').fill('{"id": "dal", "servings": 2}')
  await expect(dialog.getByRole('list', { name: 'What this does' })).toContainText('New: Dal met spinazie')
  await dialog.getByRole('button', { name: 'Add recipe' }).click()
  await expect(dialog).toBeHidden()
  await expect(page.getByText('Added 1 recipe.')).toBeVisible()
  expect(saved).toEqual({ data: { id: 'dal', servings: 2 }, replace: true })
})

test('Copy all puts every recipe and the format on the clipboard', async ({ page, context, isMobile }) => {
  await context.grantPermissions(['clipboard-read', 'clipboard-write'])
  await stub(page)
  const exported = { schema: 'hub-recipe/1', guide: 'These are my recipes', json_schema: {}, recipes: [{ id: 'kip-shoarma' }] }
  await page.route('**/api/recipes/export', (r) => r.fulfill({ json: exported }))
  await page.goto('/recipes')

  await action(page, isMobile, 'Copy all')
  await expect(page.getByText(/Copied 1 recipe and the format/)).toBeVisible()
  expect(JSON.parse(await page.evaluate(() => navigator.clipboard.readText()))).toEqual(exported)
})
