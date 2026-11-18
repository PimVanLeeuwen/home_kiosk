import { expect, test } from '@playwright/test'

const today = (() => {
  const d = new Date()
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
})()

const created = new Date().toISOString()
const PLUMBER = { id: 1, title: 'Ring the plumber', note: 'the kitchen tap', due: today, high: true, created, state: 'today' }
const SHED = { id: 2, title: 'Fix the shed', note: null, due: null, high: false, created, state: null }
let seq = 0
const answer = (todos: unknown[], extra: Record<string, unknown> = {}) => ({
  // Every answer is newer than the last, as the hub's are.
  as_of: new Date(Date.now() + ++seq).toISOString(), stale: false, today,
  open: todos.length, overdue: 0, due_today: todos.some((t) => (t as { state: string }).state === 'today') ? 1 : 0, todos, ...extra,
})

test('Todos adds one, ticks one off with Undo; Home shows them', async ({ page }) => {
  let sent: Record<string, unknown> | undefined
  let open: unknown[] = [PLUMBER]
  await page.route('**/api/todos', (route) => {
    if (route.request().method() === 'POST') {
      sent = route.request().postDataJSON()
      open = [PLUMBER, SHED]
    }
    return route.fulfill({ json: answer(open) })
  })
  await page.route('**/api/todos/2', (route) => {
    open = [PLUMBER]
    return route.fulfill({ json: answer(open, { removed: SHED }) })
  })
  await page.route('**/api/todos/restore', (route) => {
    open = [PLUMBER, SHED]
    return route.fulfill({ json: answer(open) })
  })

  await page.goto('/todos')
  await expect(page.getByRole('heading', { level: 1, name: 'Todos' })).toBeVisible()
  await expect(page.getByText('1 open, 1 today')).toBeVisible()
  await expect(page.getByText('the kitchen tap')).toBeVisible()

  const form = page.getByRole('form', { name: 'Add a todo' })
  await form.getByLabel('Title').fill('Fix the shed')
  await form.getByRole('button', { name: 'Add todo' }).click()
  await expect(page.getByRole('checkbox', { name: 'Fix the shed done' })).toBeVisible()
  expect(sent).toEqual({ title: 'Fix the shed', note: null, due: null, high: false })

  await page.getByRole('checkbox', { name: 'Fix the shed done' }).click()
  await expect(page.getByRole('checkbox', { name: 'Fix the shed done' })).toHaveCount(0)
  await page.getByRole('button', { name: 'Undo' }).click()
  await expect(page.getByRole('checkbox', { name: 'Fix the shed done' })).toBeVisible()

  await page.goto('/')
  const card = page.getByRole('region', { name: 'Todos' })
  await expect(card).toContainText('Ring the plumber')
  await expect(card).not.toContainText('the kitchen tap')
})

test('a long todo keeps its buttons on the phone screen', async ({ page, isMobile }) => {
  test.skip(!isMobile, 'the phone layout')
  const long = { ...PLUMBER, title: 'Ring the plumber about the kitchen tap that keeps dripping all night long' }
  await page.route('**/api/todos', (route) => route.fulfill({ json: answer([long]) }))
  await page.goto('/todos')
  await expect(page.getByText(long.title).first()).toBeVisible()

  const width = page.viewportSize()!.width
  for (const button of await page.getByRole('main').getByRole('button').all()) {
    const box = await button.boundingBox()
    if (box) expect(box.x + box.width, (await button.getAttribute('aria-label')) ?? '').toBeLessThanOrEqual(width)
  }
})
