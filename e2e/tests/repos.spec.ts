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

test('Repos says when the tab\'s GitHub token expires', async ({ page }) => {
  const inDays = (n: number) => new Date(Date.now() + n * 86_400_000).toISOString()
  await page.route('**/api/repos', (route) => route.fulfill({
    json: { ...REPOS, tokens: [{ owners: ['Mine', 'GEWIS'], expires_at: inDays(10.5), checked: true }] },
  }))
  await page.goto('/repos')

  await expect(page.getByText(/GitHub token \(Mine and GEWIS\) expires .* \(in 10 days\)/)).toBeVisible()
})

test('Repos opens with the Code card: activity, builds and pull requests', async ({ page }) => {
  const day = (offset: number) => {
    const d = new Date()
    d.setDate(d.getDate() - offset)
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
  }
  const minutesAgo = (n: number) => new Date(Date.now() - n * 60_000).toISOString()
  await page.route('**/api/repos', (route) => route.fulfill({
    json: {
      ...REPOS,
      activity: { login: 'PimVanLeeuwen', total: 9, error: null, days: [
        { day: day(1), count: 6, level: 4 }, { day: day(0), count: 3, level: 2 }] },
      groups: [
        { ...REPOS.groups[0], own: true, repos: [repo('home_kiosk', {
          ci: 'failing', branch: 'main', commit_message: 'fix: a thing', committed_at: minutesAgo(12), open_prs: 1,
          pulls: [{ number: 41, title: 'Code card', url: 'https://github.com/p/41', draft: false, updated_at: minutesAgo(2), ci: 'running' }],
        })] },
        { ...REPOS.groups[1], own: false, repos: [repo('aurora', { full_name: 'GEWIS/aurora', committed_at: minutesAgo(1) })] },
      ],
    },
  }))
  await page.goto('/repos')

  const card = page.getByRole('region', { name: 'Code' })
  await expect(card.getByText('1 failing')).toBeVisible()
  await expect(card.getByRole('img', { name: '9 contributions in 16 weeks' })).toBeVisible()
  await expect(card.getByRole('link', { name: /home_kiosk main · fix: a thing Failed 12 min ago/ })).toBeVisible()
  await expect(card.getByRole('link', { name: /home_kiosk #41 Code card Running/ })).toBeVisible()
  await expect(card.getByText('aurora')).toHaveCount(0)
})
