import { expect, test } from '@playwright/test'

const AI = {
  as_of: new Date().toISOString(), stale: false, configured: true, cap: 10, spent: 0.42, calls: 30, capped: false,
  features: [{ id: 'ask', label: 'Ask', on: true }],
}
const DIM = { id: 't1', tool: 'lights_change', args: { group: 'spots', brightness: 40 }, title: 'Dim the Spots to 40%', detail: 'now at 80%' }

test('Ask answers, proposes a change and makes it only after Confirm', async ({ page }) => {
  const confirmed: unknown[] = []
  await page.route('**/api/ai', (route) => route.fulfill({ json: AI }))
  await page.route('**/api/ask', (route) => {
    const { messages } = route.request().postDataJSON() as { messages: { text: string }[] }
    const last = messages[messages.length - 1].text
    return route.fulfill({
      json: last.includes('spots')
        ? { text: 'I proposed dimming the **Spots** to 40%.', used: ['lights'], proposals: [DIM], spent: 0.44, cap: 10 }
        : { text: 'Tomorrow\'s **07:16** is on time so far.\n\n- Track 8b\n- Little rain', used: ['train', 'forecast'], proposals: [], spent: 0.43, cap: 10 },
    })
  })
  await page.route('**/api/ask/confirm', (route) => {
    confirmed.push(route.request().postDataJSON())
    return route.fulfill({ json: { ok: true } })
  })

  await page.goto('/ask')
  await expect(page.getByRole('heading', { level: 1, name: 'Ask' })).toBeVisible()
  await expect(page.getByText('Ask the house')).toBeVisible()

  const box = page.getByLabel('Your question')
  await box.fill('Is my train on time tomorrow?')
  await box.press('Enter')
  const thread = page.getByRole('list', { name: 'Conversation' })
  await expect(thread.locator('strong', { hasText: '07:16' })).toBeVisible()
  await expect(thread.getByText('Track 8b')).toBeVisible()

  await box.fill('Dim the spots to 40%')
  await box.press('Enter')
  const card = page.getByRole('group', { name: 'Dim the Spots to 40%' })
  await expect(card).toContainText('now at 80%')
  expect(confirmed).toEqual([])
  await card.getByRole('button', { name: 'Confirm' }).click()
  await expect(card.getByText('Done')).toBeVisible()
  expect(confirmed).toEqual([{ tool: 'lights_change', args: { group: 'spots', brightness: 40 } }])

  // The question box stays in view, above the phone's tab bar.
  await expect(box).toBeInViewport()
  await page.getByRole('button', { name: 'New chat' }).click()
  await expect(page.getByText('Ask the house')).toBeVisible()
})
