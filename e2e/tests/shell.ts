import type { Locator, Page } from '@playwright/test'

/** Spaces of one page: no tabs, and on a phone no tab of their own (they sit under More). */
const ONE_PAGE = ['Money', 'Kitchen']

/** Page object for the Home hub shell: the top bar's spaces on desktop, the tab bar on a phone, and a space's tabs. */
export class Shell {
  readonly spaces: Locator
  readonly tabBar: Locator
  readonly main: Locator

  constructor(readonly page: Page) {
    this.spaces = page.getByRole('banner').getByRole('navigation', { name: 'Spaces' })
    this.tabBar = page.locator('nav.fixed')
    this.main = page.getByRole('main')
  }

  heading() {
    return this.main.getByRole('heading', { level: 1 })
  }

  /** A space's tabs above the page. */
  tabs(space: string) {
    return this.page.getByRole('navigation', { name: `${space} pages` })
  }

  /** Go to a space, then one of its tabs, the way a person would on this device. */
  async open(space: string, tab: string | undefined, isMobile: boolean) {
    if (isMobile && ONE_PAGE.includes(space)) {
      await this.tabBar.getByRole('link', { name: 'More' }).click()
      await this.main.getByRole('link', { name: new RegExp(tab ?? space) }).click()
      return
    }
    await (isMobile ? this.tabBar : this.spaces).getByRole('link', { name: space, exact: true }).click()
    if (tab && !ONE_PAGE.includes(space)) await this.tabs(space).getByRole('link', { name: tab, exact: true }).click()
  }

  /** Stub /api/nas so the brand shows a host name. */
  async stubNas(host = 'dev-minotaur') {
    await this.page.route('**/api/nas', (route) => route.fulfill({ json: { host } }))
  }
}
