import { expect, test, type Page } from '@playwright/test'

/** As a person would: the shortcut on a computer, the search button on a phone. */
async function openPalette(page: Page, isMobile: boolean) {
  if (isMobile) await page.getByRole('button', { name: 'Search', exact: true }).click()
  else await page.keyboard.press('ControlOrMeta+k')
}

test('the command palette finds a page by a few letters and goes there', async ({ page, isMobile }) => {
  await page.goto('/')

  await openPalette(page, isMobile)

  const palette = page.getByRole('dialog', { name: 'Search the hub' })
  await expect(palette).toBeVisible()
  const field = palette.getByRole('combobox', { name: 'Search pages and settings' })
  await expect(field).toBeFocused()
  await field.fill('bk')
  await expect(palette.getByRole('option', { selected: true })).toContainText('Backups')
  await field.press('Enter')

  await expect(page).toHaveURL('/backups')
  await expect(palette).toBeHidden()
})

test('the command palette goes to a Settings section and keeps it as recent', async ({ page, isMobile }) => {
  await page.goto('/')
  await openPalette(page, isMobile)
  const palette = page.getByRole('dialog', { name: 'Search the hub' })
  await palette.getByRole('combobox').fill('feeds')
  await palette.getByRole('option', { name: /News feeds/ }).click()
  await expect(page).toHaveURL('/settings/feeds')
  await expect(page.getByRole('heading', { level: 1 })).toHaveText('Settings')

  await openPalette(page, isMobile)
  await expect(palette.getByText('Recent')).toBeVisible()
  await page.keyboard.press('Escape')
  await expect(palette).toBeHidden()
})
