import { expect, test } from '@playwright/test'
import { Shell } from './shell'

test.describe('desktop navigation', () => {
  test.skip(({ isMobile }) => isMobile, 'sidebar is desktop only')

  test('sidebar moves between sections and marks the current one', async ({ page }) => {
    const shell = new Shell(page)
    await page.goto('/')
    await expect(shell.tabBar).toBeHidden()

    await shell.sidebar.getByRole('link', { name: 'Backups' }).click()

    await expect(page).toHaveURL('/backups')
    await expect(shell.heading()).toHaveText('Backups')
    await expect(page).toHaveTitle('Backups · Home hub')
    await expect(shell.sidebar.getByRole('link', { name: 'Backups' })).toHaveAttribute(
      'aria-current',
      'page',
    )
  })

  test('shows the NAS host under the brand when the collector answers', async ({ page }) => {
    const shell = new Shell(page)
    await shell.stubNas()
    await page.goto('/')

    await expect(page.locator('aside').getByText('dev-minotaur')).toBeVisible()
  })

  test('leaves the host out when the collector is down', async ({ page }) => {
    await page.goto('/')

    await expect(page.locator('aside').getByText('Home hub')).toBeVisible()
    await expect(page.getByText('dev-minotaur')).toHaveCount(0)
  })
})

test.describe('mobile navigation', () => {
  test.skip(({ isMobile }) => !isMobile, 'tab bar is mobile only')

  test('tab bar reaches the main sections', async ({ page }) => {
    const shell = new Shell(page)
    await page.goto('/')
    await expect(shell.sidebar).toBeHidden()

    await shell.tabBar.getByRole('link', { name: 'Portfolio' }).click()

    await expect(page).toHaveURL('/portfolio')
    await expect(shell.heading()).toHaveText('Portfolio')
  })

  test('More lists the other sections and stays highlighted inside them', async ({ page }) => {
    const shell = new Shell(page)
    await page.goto('/')

    await shell.tabBar.getByRole('link', { name: 'More' }).click()
    await expect(shell.heading()).toHaveText('More')
    await shell.main.getByRole('link', { name: /Alerts/ }).click()

    await expect(page).toHaveURL('/alerts')
    await expect(shell.heading()).toHaveText('Alerts')
    await expect(shell.tabBar.getByRole('link', { name: 'More' })).toHaveAttribute(
      'aria-current',
      'page',
    )
  })
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
