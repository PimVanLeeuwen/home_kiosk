import { expect, test } from '@playwright/test'
import { Shell } from './shell'

test.describe('desktop navigation', () => {
  test.skip(({ isMobile }) => isMobile, 'the top bar holds the spaces on desktop')

  test('the top bar moves between spaces, the tabs between their pages', async ({ page }) => {
    const shell = new Shell(page)
    await page.goto('/')
    await expect(shell.tabBar).toBeHidden()

    await shell.spaces.getByRole('link', { name: 'House' }).click()
    await expect(page).toHaveURL('/house')
    await expect(shell.heading()).toHaveText('House')
    await shell.tabs('House').getByRole('link', { name: 'Backups' }).click()

    await expect(page).toHaveURL('/house/backups')
    await expect(shell.heading()).toHaveText('Backups')
    await expect(page).toHaveTitle('Backups · Home hub')
    await expect(shell.spaces.getByRole('link', { name: 'House' })).toHaveAttribute('aria-current', 'page')
    await expect(shell.tabs('House').getByRole('link', { name: 'Backups' })).toHaveAttribute('aria-current', 'page')
  })

  test('Settings sits behind the menu, Ask beside it', async ({ page }) => {
    const shell = new Shell(page)
    await page.goto('/')

    await page.getByRole('banner').getByRole('button', { name: 'Menu' }).click()
    await page.getByRole('banner').getByRole('link', { name: 'Settings' }).click()
    await expect(page).toHaveURL('/settings/services')
    await page.getByRole('banner').getByRole('link', { name: 'Ask' }).click()
    await expect(shell.heading()).toHaveText('Ask')
  })

  test('shows the NAS host under the brand when the collector answers', async ({ page }) => {
    const shell = new Shell(page)
    await shell.stubNas()
    await page.goto('/')

    await expect(page.getByRole('banner').getByText('dev-minotaur')).toBeVisible()
  })

  test('leaves the host out when the collector is down', async ({ page }) => {
    await page.goto('/')

    await expect(page.getByRole('banner').getByText('Home hub')).toBeVisible()
    await expect(page.getByText('dev-minotaur')).toHaveCount(0)
  })
})

test.describe('mobile navigation', () => {
  test.skip(({ isMobile }) => !isMobile, 'the tab bar is for a phone')

  test('the tab bar reaches the spaces and marks the current one', async ({ page }) => {
    const shell = new Shell(page)
    await page.goto('/')
    await expect(shell.spaces).toBeHidden()

    await shell.tabBar.getByRole('link', { name: 'Read' }).click()
    await expect(page).toHaveURL('/read/news')
    await shell.tabs('Read').getByRole('link', { name: 'Saved' }).click()

    await expect(page).toHaveURL('/read/saved')
    await expect(shell.tabBar.getByRole('link', { name: 'Read' })).toHaveAttribute('aria-current', 'page')
  })

  test('More lists the other spaces and stays highlighted inside them', async ({ page }) => {
    const shell = new Shell(page)
    await page.goto('/')

    await shell.tabBar.getByRole('link', { name: 'More' }).click()
    await expect(shell.heading()).toHaveText('More')
    await shell.main.getByRole('link', { name: /Portfolio/ }).click()

    await expect(page).toHaveURL('/money/portfolio')
    await expect(shell.tabBar.getByRole('link', { name: 'More' })).toHaveAttribute('aria-current', 'page')
  })

  test('Ask is in the top bar', async ({ page }) => {
    const shell = new Shell(page)
    await page.goto('/')

    await page.getByRole('banner').getByRole('link', { name: 'Ask' }).click()
    await expect(page).toHaveURL('/ask')
    await expect(shell.heading()).toHaveText('Ask')
  })
})

test('an old address lands on its page in its space, query and all', async ({ page }) => {
  const shell = new Shell(page)

  await page.goto('/backups')
  await expect(page).toHaveURL('/house/backups')
  await expect(shell.heading()).toHaveText('Backups')

  await page.goto('/tailscale')
  await expect(page).toHaveURL('/house/network')

  await page.goto('/news?group=tech')
  await expect(page).toHaveURL('/read/news?group=tech')
})

test('Home\'s tabs reach the pages built from Today\'s cards', async ({ page, isMobile }) => {
  const shell = new Shell(page)
  await page.goto('/')

  for (const [tab, url] of [['Air', '/home/air'], ['Laundry', '/home/laundry'], ['Apple devices', '/home/apple']]) {
    await shell.open('Home', tab, isMobile)
    await expect(page).toHaveURL(url)
    await expect(shell.heading()).toHaveText(tab)
  }
})

test('deep links and reloads land on the right section', async ({ page }) => {
  const shell = new Shell(page)
  await page.goto('/settings')
  await page.reload()

  await expect(shell.heading()).toHaveText('Settings')
})

test('unknown addresses show the not-found page', async ({ page }) => {
  const shell = new Shell(page)
  await page.goto('/nope')

  await expect(shell.heading()).toHaveText('Page not found')
  await shell.main.getByRole('link', { name: 'Back to Home' }).click()
  await expect(page).toHaveURL('/')
  await expect(page).toHaveTitle('Home · Home hub')
})
