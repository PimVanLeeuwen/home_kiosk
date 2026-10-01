import { expect, test } from '@playwright/test'

const SETTINGS = {
  routing: { backup: 'nas', updates: 'nas', uptime: 'nas', rules: 'nas', portfolio: 'portfolio', manual: 'nas' },
  quiet: { enabled: true, start: '23:00', end: '07:00' },
  categories: { backup: 'Backups', updates: 'Container updates', uptime: 'Uptime Kuma', rules: 'Hub alert rules', portfolio: 'Portfolio', manual: 'Sent from the hub' },
  chats: [{ key: 'nas', label: 'NAS alerts', configured: true }, { key: 'portfolio', label: 'Portfolio', configured: true }],
  token_set: true, notify_key_set: true,
}

test('Alerts lists messages and sends one', async ({ page }) => {
  const sent: unknown[] = []
  await page.route('**/api/alerts/settings', (r) => r.fulfill({ json: SETTINGS }))
  await page.route('**/api/alerts/rules', (r) => r.fulfill({ json: { rules: { disk_space: { enabled: true, threshold_pct: 90 } }, labels: { disk_space: 'Disk space' } } }))
  await page.route('**/api/alerts/incidents', (r) => r.fulfill({ json: [] }))
  await page.route('**/api/alerts/messages**', (r) => r.fulfill({ json: [
    { id: 1, ts: new Date().toISOString(), source: 'backup', category: 'backup', severity: 'ok', title: 'NAS backup OK', body: 'volume1 4 min', chat: 'nas', status: 'sent', error: null, sent_at: null },
  ] }))
  await page.route('**/api/alerts/send', (r) => {
    sent.push(r.request().postDataJSON())
    return r.fulfill({ json: { id: 2, ts: new Date().toISOString(), source: 'hub', category: 'manual', severity: 'info', title: 'Hello', body: '', chat: 'nas', status: 'sent', error: null, sent_at: null } })
  })
  await page.goto('/alerts')

  await expect(page.getByRole('region', { name: 'Messages' })).toContainText('NAS backup OK')
  await expect(page.getByRole('region', { name: 'Open alerts' })).toContainText('Nothing needs a look')
  const form = page.getByRole('form', { name: 'Send a message' })
  await form.getByLabel('Message', { exact: true }).fill('Hello')
  await form.getByRole('button', { name: 'Send' }).click()
  await expect.poll(() => sent).toEqual([{ chat: 'nas', text: 'Hello' }])
})
