import { expect, test } from '@playwright/test'
import { Shell } from './shell'

const device = (d: Record<string, unknown>) => ({
  ipv6: null, last_seen: null, connection: null, relay: null, endpoint: null, exit_node: false, rx_bytes: 0, tx_bytes: 0,
  dns_name: `${d.name}.tail1234.ts.net`, ...d,
})

const TAILNET = {
  as_of: new Date().toISOString(),
  stale: false,
  name: 'tail1234',
  health: ["Tailscale can't reach the configured DNS servers."],
  self: device({ name: 'dev-minotaur', os: 'linux', online: true, ipv4: '100.70.0.10', relay: 'ams' }),
  peers: [
    device({ name: 'appletv', os: 'tvOS', online: true, ipv4: '100.64.9.17', connection: 'direct', endpoint: '192.168.1.40:41641', exit_node: true }),
    device({ name: 'pim-iphone', os: 'iOS', online: true, ipv4: '100.88.3.51', connection: 'relay', relay: 'ams' }),
    device({ name: 'desk-pc', os: 'windows', online: false, ipv4: '100.102.7.88', last_seen: new Date(Date.now() - 5 * 3_600_000).toISOString() }),
  ],
}

test('Tailscale shows the tailnet, its health and every device', async ({ page }) => {
  await page.route('**/api/tailnet', (route) => route.fulfill({ json: TAILNET }))
  await page.goto('/tailscale')
  const shell = new Shell(page)

  await expect(shell.heading()).toHaveText('Tailscale')
  await expect(page.getByText('tail1234 · 3 of 4 online')).toBeVisible()
  await expect(page.getByRole('alert')).toContainText("can't reach the configured DNS servers")
  await expect(page.getByRole('figure', { name: 'The NAS and 3 devices' })).toBeVisible()
  await expect(page.getByRole('region', { name: /Offline/ })).toContainText('last seen 5 hours ago')

  const phone = page.getByRole('button', { name: /pim-iphone/ })
  await phone.click()
  await expect(phone).toHaveAttribute('aria-expanded', 'true')
  await expect(page.getByText('through the relay in Amsterdam')).toBeVisible()
})

test('Tailscale is reachable from the navigation', async ({ page, isMobile }) => {
  await page.route('**/api/tailnet', (route) => route.fulfill({ json: TAILNET }))
  const shell = new Shell(page)
  await page.goto('/')

  if (isMobile) {
    await shell.tabBar.getByRole('link', { name: 'More' }).click()
    await shell.main.getByRole('link', { name: /Tailscale/ }).click()
  } else {
    await shell.sidebar.getByRole('link', { name: 'Tailscale' }).click()
  }

  await expect(page).toHaveURL('/tailscale')
  await expect(page).toHaveTitle('Tailscale · Home hub')
})
