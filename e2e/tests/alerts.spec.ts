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
  await expect(page.getByRole('region', { name: 'Open alerts' })).toContainText('All quiet')
  const form = page.getByRole('form', { name: 'Send a message' })
  await form.getByLabel('Message', { exact: true }).fill('Hello')
  await form.getByRole('button', { name: 'Send' }).click()
  await expect.poll(() => sent).toEqual([{ chat: 'nas', text: 'Hello' }])
})

test('Alerts shows ntfy delivery and switches it off', async ({ page }) => {
  const saved: Record<string, unknown>[] = []
  const settings = { ...SETTINGS, ntfy: { configured: true, enabled: true } }
  await page.route('**/api/alerts/settings', (r) => {
    if (r.request().method() === 'PUT') saved.push(r.request().postDataJSON())
    return r.fulfill({ json: settings })
  })
  await page.route('**/api/alerts/rules', (r) => r.fulfill({ json: { rules: {}, labels: {} } }))
  await page.route('**/api/alerts/incidents', (r) => r.fulfill({ json: [] }))
  await page.route('**/api/alerts/messages**', (r) => r.fulfill({ json: [
    { id: 2, ts: new Date().toISOString(), source: 'rule.disk_space', category: 'rules', severity: 'warning', title: 'volume2 is 91% full', body: '500 GB left', chat: 'nas', status: 'sent', error: null, sent_at: null, channel: 'ntfy', ntfy_id: 'a1' },
    { id: 1, ts: new Date().toISOString(), source: 'backup', category: 'backup', severity: 'ok', title: 'NAS backup OK', body: '', chat: 'nas', status: 'sent', error: 'ntfy failed: ntfy not reachable', sent_at: null, channel: 'telegram' },
  ] }))
  await page.goto('/alerts')

  const log = page.getByRole('region', { name: 'Messages' })
  await expect(log).toContainText('Sent to your phone (ntfy)')
  await expect(log).toContainText('Sent to NAS alerts on Telegram; ntfy failed: ntfy not reachable')
  const delivery = page.getByRole('region', { name: 'Delivery' })
  const toggle = delivery.getByRole('switch', { name: 'Send through ntfy' })
  await expect(toggle).toHaveAttribute('aria-checked', 'true')
  await toggle.click()
  await delivery.getByRole('button', { name: 'Save' }).click()
  await expect.poll(() => saved.map((body) => body.ntfy)).toEqual([false])
})
