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

test('a message opens on its own page and is explained there', async ({ page }) => {
  const now = Date.now()
  const ago = (min: number) => new Date(now - min * 60_000).toISOString()
  await page.route('**/api/alerts/messages/7', (r) => r.fulfill({ json: {
    id: 7, ts: ago(30), source: 'rule.container_health', category: 'rules', severity: 'error', title: 'sonarr is down',
    body: 'Exit code 137.', chat: 'nas', status: 'sent', error: null, sent_at: ago(30), channel: 'ntfy', ntfy_id: 'n1',
    incident: 'down:sonarr', expired: false, expires_at: new Date(now + 7 * 86_400_000).toISOString(),
    html: '<b>ERROR</b> · <b>sonarr is down</b>\nExit code <code>137</code>.',
    state: { open: true, opened_at: ago(32), resolved_at: null },
    earlier: [{ id: 7, ts: ago(30), severity: 'error', title: 'sonarr is down' }, { id: 3, ts: ago(3000), severity: 'ok', title: 'Resolved: sonarr is down' }],
    links: [{ label: 'Docker page', page: '/docker', hint: '' }], explanation: null, can_explain: true, picture: true,
  } }))
  // A tiny JPEG stands in for the painted picture.
  await page.route('**/api/alerts/messages/7/picture', (r) => r.fulfill({ contentType: 'image/jpeg', body: Buffer.from('/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsLDBkSEw8UHRofHh0aHBwgJC4nICIsIxwcKDcpLDAxNDQ0Hyc5PTgyPC4zNDL/2wBDAQkJCQwLDBgNDRgyIRwhMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjL/wAARCAACAAMDASIAAhEBAxEB/8QAHwAAAQUBAQEBAQEAAAAAAAAAAAECAwQFBgcICQoL/8QAtRAAAgEDAwIEAwUFBAQAAAF9AQIDAAQRBRIhMUEGE1FhByJxFDKBkaEII0KxwRVS0fAkM2JyggkKFhcYGRolJicoKSo0NTY3ODk6Q0RFRkdISUpTVFVWV1hZWmNkZWZnaGlqc3R1dnd4eXqDhIWGh4iJipKTlJWWl5iZmqKjpKWmp6ipqrKztLW2t7i5usLDxMXGx8jJytLT1NXW19jZ2uHi4+Tl5ufo6erx8vP09fb3+Pn6/8QAHwEAAwEBAQEBAQEBAQAAAAAAAAECAwQFBgcICQoL/8QAtREAAgECBAQDBAcFBAQAAQJ3AAECAxEEBSExBhJBUQdhcRMiMoEIFEKRobHBCSMzUvAVYnLRChYkNOEl8RcYGRomJygpKjU2Nzg5OkNERUZHSElKU1RVVldYWVpjZGVmZ2hpanN0dXZ3eHl6goOEhYaHiImKkpOUlZaXmJmaoqOkpaanqKmqsrO0tba3uLm6wsPExcbHyMnK0tPU1dbX2Nna4uPk5ebn6Onq8vP09fb3+Pn6/9oADAMBAAIRAxEAPwDbooor5A9w/9k=', 'base64') }))
  await page.route('**/api/alerts/messages/7/explain', (r) => r.fulfill({ json: { cause: 'Killed for memory.', todo: 'Start it again.', asked_at: ago(0) } }))
  await page.goto('/alerts/7')

  await expect(page.getByRole('heading', { name: 'sonarr is down' })).toBeVisible()
  await expect(page.getByText('Still open')).toBeVisible()
  const picture = page.getByRole('img', { name: 'The picture sent with this message' })
  await expect(picture).toBeVisible()
  await expect.poll(() => picture.evaluate((img: HTMLImageElement) => img.naturalWidth)).toBe(3)
  await expect(page.getByRole('region', { name: 'Earlier' })).toContainText('Resolved: sonarr is down')
  await page.getByRole('button', { name: 'Explain' }).click()
  await expect(page.getByRole('region', { name: 'Explained' })).toContainText('Killed for memory.')
  await page.getByRole('link', { name: 'Alerts', exact: true }).first().click()
  await expect(page).toHaveURL(/\/alerts$/)
})
