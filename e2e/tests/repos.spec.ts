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
