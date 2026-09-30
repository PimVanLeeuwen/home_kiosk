import type { Locator, Page } from '@playwright/test'

/** Page object for the Home hub shell: sidebar on desktop, tab bar on mobile. */
export class Shell {
  readonly sidebar: Locator
  readonly tabBar: Locator
  readonly main: Locator

  constructor(readonly page: Page) {
    this.sidebar = page.locator('aside').getByRole('navigation', { name: 'Sections' })
    this.tabBar = page.locator('nav.fixed')
    this.main = page.getByRole('main')
  }

  heading() {
    return this.main.getByRole('heading', { level: 1 })
  }

  /** Stub /api/nas so the brand shows a host name. */
  async stubNas(host = 'dev-minotaur') {
    await this.page.route('**/api/nas', (route) => route.fulfill({ json: { host } }))
  }
}
