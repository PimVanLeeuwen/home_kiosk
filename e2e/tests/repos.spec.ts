import { expect, test } from '@playwright/test'

const repo = (name: string, over: Record<string, unknown> = {}) => ({
  name, full_name: `PimVanLeeuwen/${name}`, url: `https://github.com/PimVanLeeuwen/${name}`,
  description: `${name} description`, private: false, fork: false, language: 'Python',
  language_color: '#3572A5', stars: 1, forks: 0, pushed_at: new Date().toISOString(),
  open_prs: 0, open_issues: 0, ci: 'passing', release: null, ...over,
})

const REPOS = {
  as_of: new Date().toISOString(),
  stale: false,
  groups: [
    { login: 'PimVanLeeuwen', label: 'Mine', error: null, repos: [repo('home_kiosk', { private: true }), repo('a-fork', { fork: true })] },
    { login: 'GEWIS', label: 'GEWIS', error: null, repos: [repo('aurora', { full_name: 'GEWIS/aurora', ci: 'failing' })] },
  ],
}

test('Repos lists owners in tabs with forks behind a switch', async ({ page, isMobile }) => {
  await page.route('**/api/repos', (route) => route.fulfill({ json: REPOS }))
  await page.goto('/')

  // Reachable from the sidebar on desktop and from More on mobile.
  if (isMobile) {
    await page.locator('nav.fixed').getByRole('link', { name: 'More' }).click()
    await page.getByRole('main').getByRole('link', { name: /Repos/ }).click()
  } else {
    await page.locator('aside').getByRole('link', { name: 'Repos' }).click()
  }

  await expect(page.getByRole('tab', { name: 'Mine 1', selected: true })).toBeVisible()
  await expect(page.getByRole('article')).toHaveCount(1)
  await page.getByRole('switch').click()
  await expect(page.getByRole('article')).toHaveCount(2)

  await page.getByRole('tab', { name: /GEWIS/ }).click()
  await expect(page).toHaveURL(/\?tab=GEWIS$/)
  await expect(page.getByRole('article', { name: /aurora/ })).toContainText('CI failing')
})

test('Repos shows the backup status of mirrored owners', async ({ page }) => {
  await page.route('**/api/repos', (route) => route.fulfill({ json: REPOS }))
  await page.route('**/api/github-mirror', (route) =>
    route.fulfill({
      json: {
        as_of: new Date().toISOString(), stale: false, enabled: true, dir: '/backups/github', error: null,
        owners: [{ login: 'PimVanLeeuwen', label: 'Mine', removed: [], error: null, repos: [
          { full_name: 'PimVanLeeuwen/home_kiosk', archived: false, ok: true, error: null, mirrored_at: new Date().toISOString(), bytes: 1 },
        ] }],
        runs: [{ started: new Date().toISOString(), finished: new Date().toISOString(), ok: true, repos: 1, failed: 0, removed: 0, bytes: 1 }],
        last_success: new Date().toISOString(), next_due: null,
      },
    }),
  )
  await page.goto('/repos')

  await expect(page.getByRole('article', { name: /home_kiosk/ })).toContainText('Backed up')
  await expect(page.getByText(/Backed up nightly to the NAS and Hetzner: 1 repo,/)).toBeVisible()
  await page.getByRole('tab', { name: /GEWIS/ }).click()
  await expect(page.getByRole('article', { name: /aurora/ })).not.toContainText('Backed up')
})
