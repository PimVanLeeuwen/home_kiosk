import { expect, test, type Page } from '@playwright/test'

const ago = (minutes: number) => new Date(Date.now() - minutes * 60_000).toISOString()
const NAMES: [string, string][] = [
  ['github', 'GitHub'], ['cloudflare', 'Cloudflare'], ['docker', 'Docker Hub'], ['tailscale', 'Tailscale'],
  ['hetzner', 'Hetzner'], ['transip', 'TransIP'], ['proton', 'Proton'],
]

function outside(over: Record<string, object> = {}) {
  return {
    as_of: ago(1), stale: false,
    services: NAMES.map(([key, name]) => ({
      key, name, url: `https://status.${key}.test`, state: 'ok', incidents: [], as_of: ago(1), stale: false, error: null,
      ...over[key],
    })),
  }
}

const ACTIONS_DELAYED = {
  state: 'degraded',
  incidents: [{
    title: 'Actions runs are delayed', impact: 'degraded', status: 'identified', started_at: ago(24),
    url: 'https://stspg.io/actions',
    updates: [
      { at: ago(22), status: 'investigating', text: 'We are investigating reports of delayed runs.' },
      { at: ago(9), status: 'identified', text: 'Workflow runs are delayed; a fix is rolling out.' },
    ],
  }],
}

const serve = (page: Page, json: object) =>
  page.route('**/api/outside-services', (route) => route.fulfill({ json }))

test('Home shows the outside services around a check when all is well', async ({ page }) => {
  await serve(page, outside())
  await page.goto('/')

  const card = page.getByRole('region', { name: 'Outside services' })
  await expect(card).toContainText('All operational')
  await expect(card.getByRole('listitem')).toHaveCount(7)
})

test('Home leads with an outside incident and its timeline', async ({ page }) => {
  await serve(page, outside({ github: ACTIONS_DELAYED }))
  await page.goto('/')

  const incident = page.getByRole('article', { name: 'GitHub: Actions runs are delayed' })
  await expect(incident).toContainText('Degraded · for 24 min')
  await expect(incident.getByRole('list', { name: 'Timeline' }).getByRole('listitem')).toHaveCount(2)
  await expect(page.getByText('The other 6 are operational')).toBeVisible()
})

test('the Services page lists every outside service and the open incidents', async ({ page }) => {
  await serve(page, outside({ github: ACTIONS_DELAYED }))
  await page.goto('/services')

  const section = page.getByRole('region', { name: 'Outside services' })
  await expect(section.getByRole('link', { name: /open the status page/ })).toHaveCount(7)
  await expect(section.getByRole('link', { name: 'GitHub: Degraded, open the status page' })).toBeVisible()
  await expect(section.getByRole('article', { name: 'GitHub: Actions runs are delayed' })).toBeVisible()
})
