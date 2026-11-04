import { expect, test } from '@playwright/test'

const today = (() => {
  const d = new Date()
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
})()

const BINS = {
  id: 1, title: 'Bins out', start: today, at: '07:30', notify: 'evening', next: today,
  repeat: { kind: 'every', every: 2, unit: 'weeks', weekdays: [], day: 1 },
}
const answer = (reminders: unknown[], done = false) => ({
  as_of: new Date().toISOString(), stale: false, today,
  due: [{ id: 1, title: 'Bins out', at: '07:30', done }], reminders,
})

test('Reminders adds one and ticks today\'s off; Home shows them', async ({ page }) => {
  let sent: Record<string, unknown> | undefined
  await page.route('**/api/reminders', (route) => {
    if (route.request().method() === 'POST') {
      sent = route.request().postDataJSON()
      return route.fulfill({ json: answer([BINS, { ...BINS, id: 2, title: 'Water the plants', at: null, notify: 'at', repeat: { ...BINS.repeat, kind: 'weekly', weekdays: [0] } }]) })
    }
    return route.fulfill({ json: answer([BINS]) })
  })
  await page.route('**/api/reminders/1/done', (route) => route.fulfill({ json: answer([BINS], true) }))

  await page.goto('/reminders')
  await expect(page.getByRole('heading', { level: 1, name: 'Reminders' })).toBeVisible()
  await expect(page.getByText('Every 2 weeks · Message the evening before')).toBeVisible()

  const form = page.getByRole('form', { name: 'Add a reminder' })
  await form.getByLabel('Title').fill('Water the plants')
  await form.getByRole('radio', { name: 'Weekly' }).click()
  await form.getByRole('button', { name: 'Mon' }).click()
  await form.getByRole('button', { name: 'Add reminder' }).click()
  await expect(page.getByText('Every Mon · Message at 08:00')).toBeVisible()
  expect(sent).toMatchObject({ title: 'Water the plants', repeat: { kind: 'weekly', weekdays: [0] } })

  await page.getByRole('checkbox', { name: 'Bins out done' }).click()
  await expect(page.getByRole('checkbox', { name: 'Bins out done' })).toHaveAttribute('aria-checked', 'true')

  await page.goto('/')
  await expect(page.getByRole('region', { name: 'Reminders' })).toContainText('Bins out')
})
