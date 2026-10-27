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

const ingredient = (name: string, amount: number | null, unit = '', pantry = false) => ({ name, amount, unit, note: null, pantry })
const DETAIL = {
  recipe: {
    schema: 'hub-recipe/1', id: 'kip-shoarma', title: 'Kip shoarma uit de oven', intro: 'Met knoflooksaus.', servings: 2,
    tags: ['oven'], source: null, times: { prep_min: 20, cook_min: 30 }, notes: null,
    phases: [
      { name: 'Marinade', kind: 'prep', steps: [{ text: 'Snijd de kip.', ingredients: [ingredient('kippendijen', 500, 'g'), ingredient('komijn', 1, 'tl', true)] }] },
      { name: 'Oven', kind: 'cook', steps: [{ text: 'Oven op 220 °C, 25 minuten.', ingredients: [] }] },
    ],
  },
  needs_review: false, created_at: '2026-10-27T18:00:00+00:00', updated_at: '2026-10-27T18:00:00+00:00', previous_at: null,
  photo: '2026-10-27T18:00:00+00:00',
}

test('a recipe shows what to get and check, scales, and puts the heat after the prep', async ({ page }) => {
  await stub(page)
  await page.route('**/api/recipes/kip-shoarma', (r) => r.fulfill({ json: DETAIL }))
  await page.goto('/recipes')
  await page.getByRole('list', { name: 'Recipes' }).getByRole('link', { name: /Kip shoarma/ }).click()

  await expect(page).toHaveTitle('Kip shoarma uit de oven · Home hub')
  await expect(page.getByRole('region', { name: 'To get' })).toContainText('500 g')
  await expect(page.getByRole('region', { name: 'Check' })).toContainText('komijn')
  await expect(page.getByRole('separator', { name: 'All prepped, now the heat' })).toBeVisible()
  await page.getByRole('button', { name: 'More persons' }).click()
  await page.getByRole('button', { name: 'More persons' }).click()
  await expect(page.getByRole('region', { name: 'To get' })).toContainText('1 kg')
})

test('a photo from the device is shrunk in the browser and sent as JSON', async ({ page }) => {
  let sent: { data: string } | null = null
  await page.route('**/api/recipes/kip-shoarma', (r) => r.fulfill({ json: DETAIL }))
  await page.route('**/api/recipes/kip-shoarma/photo/*', (r) => r.fulfill({ body: PNG, contentType: 'image/png' }))
  await page.route('**/api/recipes/kip-shoarma/photo', (r) => {
    sent = r.request().postDataJSON()
    r.fulfill({ json: DETAIL })
  })
  await page.goto('/recipes/kip-shoarma')

  await page.getByLabel('Photo').setInputFiles({ name: 'pan.png', mimeType: 'image/png', buffer: PNG })
  await expect(page.getByText('The photo is in.')).toBeVisible()
  expect(sent!.data).toMatch(/^data:image\/jpeg;base64,/)
})

test('deleting a recipe asks once more, then goes back to the list', async ({ page }) => {
  await stub(page)
  let deleted = false
  await page.route('**/api/recipes/kip-shoarma', (r) => {
    if (r.request().method() === 'DELETE') {
      deleted = true
      return r.fulfill({ json: { deleted: 'kip-shoarma' } })
    }
    return r.fulfill({ json: DETAIL })
  })
  await page.goto('/recipes/kip-shoarma')

  await page.getByRole('button', { name: 'Recipe actions' }).click()
  await page.getByRole('menuitem', { name: /Delete recipe/ }).click()
  await page.getByRole('alert').getByRole('button', { name: 'Delete for good' }).click()
  await expect(page).toHaveURL('/recipes')
  await expect(page.getByText('Deleted "Kip shoarma uit de oven".')).toBeVisible()
  expect(deleted).toBe(true)
})

test('cook mode goes phase by phase, pauses before the heat and keeps its place on a reload', async ({ page }) => {
  await page.route('**/api/recipes/kip-shoarma', (r) => r.fulfill({ json: DETAIL }))
  await page.route('**/api/recipes/kip-shoarma/photo/*', (r) => r.fulfill({ body: PNG, contentType: 'image/png' }))
  await page.goto('/recipes/kip-shoarma')
  await page.getByRole('button', { name: 'More persons' }).click()
  await page.getByRole('main').getByRole('link', { name: /^Cook/ }).filter({ visible: true }).click()

  const cook = page.getByRole('dialog', { name: 'Cooking Kip shoarma uit de oven' })
  await expect(cook.getByRole('heading', { name: 'Marinade' })).toBeVisible()
  await expect(cook).toContainText('750 g')
  await cook.getByRole('button', { name: /Snijd de kip/ }).click()
  await expect(cook.getByRole('button', { name: /Snijd de kip/ })).toHaveAttribute('aria-pressed', 'true')
  await page.getByRole('button', { name: 'All prepped' }).click()
  await expect(cook.getByRole('heading', { name: 'All prepped' })).toBeVisible()
  await page.getByRole('button', { name: 'Start cooking' }).click()
  await expect(cook.getByRole('heading', { name: 'Oven' })).toBeVisible()

  await page.reload()
  await expect(cook.getByRole('heading', { name: 'Oven' })).toBeVisible()
  await page.getByRole('button', { name: 'Previous phase' }).click()
  await page.getByRole('button', { name: 'Back to prep' }).click()
  await expect(cook.getByRole('button', { name: /Snijd de kip/ })).toHaveAttribute('aria-pressed', 'true')
  await page.getByRole('link', { name: 'Close cook mode' }).click()
  await expect(page).toHaveURL('/recipes/kip-shoarma?persons=3')
})
