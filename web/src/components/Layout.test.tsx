import { fireEvent, screen, waitFor, within } from '@testing-library/react'
import { vi } from 'vitest'
import { renderRoute } from '../test/renderRoute'
import { stubApi } from '../test/stubApi'

function stubNas(body: unknown, ok = true) {
  vi.stubGlobal(
    'fetch',
    vi.fn(() => Promise.resolve(new Response(JSON.stringify(body), { status: ok ? 200 : 503 }))),
  )
}

const topBar = () => screen.getByRole('banner')
const spaces = () => screen.getAllByRole('navigation', { name: 'Spaces' })[0]
const tabBar = () => screen.getAllByRole('navigation', { name: 'Spaces' })[1]
const names = (nav: HTMLElement) => within(nav).getAllByRole('link').map((link) => link.textContent)

describe('Layout', () => {
  it('shows the six spaces in the top bar, with Ask beside them', () => {
    renderRoute('/')

    expect(names(spaces())).toEqual(['Now', 'Home', 'House', 'Read', 'Money', 'Kitchen'])
    expect(within(topBar()).getByRole('link', { name: 'Ask' })).toHaveAttribute('href', '/ask')
  })

  it('marks the current space on any of its pages, and its tab', () => {
    renderRoute('/house/backups')

    expect(within(spaces()).getByRole('link', { name: 'House' })).toHaveAttribute('aria-current', 'page')
    expect(within(spaces()).getByRole('link', { name: 'Now' })).not.toHaveAttribute('aria-current')
    const tabs = screen.getByRole('navigation', { name: 'House pages' })
    expect(names(tabs)).toEqual(['Overview', 'NAS', 'Docker', 'Services', 'Backups', 'Media', 'Network', 'Repos', 'Alerts'])
    expect(within(tabs).getByRole('link', { name: 'Backups' })).toHaveAttribute('aria-current', 'page')
    expect(within(tabs).getByRole('link', { name: 'NAS' })).not.toHaveAttribute('aria-current')
    // The overview is current only on its own address, not on every House page.
    expect(within(tabs).getByRole('link', { name: 'Overview' })).not.toHaveAttribute('aria-current')
  })

  it('shows no tabs for a space with one page, nor on Ask', () => {
    renderRoute('/money/portfolio')
    expect(screen.queryByRole('navigation', { name: /pages$/ })).toBeNull()
  })

  it('keeps Settings behind the menu', () => {
    renderRoute('/')

    const menu = within(topBar()).getByRole('button', { name: 'Menu' })
    expect(screen.queryByRole('link', { name: 'Settings' })).toBeNull()
    fireEvent.click(menu)
    expect(menu).toHaveAttribute('aria-expanded', 'true')
    expect(within(topBar()).getByRole('link', { name: 'Settings' })).toHaveAttribute('href', '/settings')
    fireEvent.keyDown(document, { key: 'Escape' })
    expect(menu).toHaveAttribute('aria-expanded', 'false')
  })

  it('shows four spaces plus More in the phone tab bar', () => {
    renderRoute('/')

    expect(names(tabBar())).toEqual(['Now', 'Home', 'House', 'Read', 'More'])
    expect(within(tabBar()).getByRole('link', { name: 'Now' })).toHaveAttribute('aria-current', 'page')
  })

  it('marks a space in the tab bar on any of its pages', () => {
    renderRoute('/house/alerts')

    expect(within(tabBar()).getByRole('link', { name: 'House' })).toHaveAttribute('aria-current', 'page')
    expect(within(tabBar()).getByRole('link', { name: 'More' })).not.toHaveAttribute('aria-current')
  })

  it('highlights More on a page that lives under it', () => {
    renderRoute('/money/portfolio')

    expect(within(tabBar()).getByRole('link', { name: 'More' })).toHaveAttribute('aria-current', 'page')
    expect(within(tabBar()).getByRole('link', { name: 'Now' })).not.toHaveAttribute('aria-current')
  })

  it('shows the NAS host name under the brand once the collector answers', async () => {
    stubNas({ host: 'dev-minotaur' })
    // A page without data of its own, so only the layout reads /api/nas.
    renderRoute('/more')

    expect(await within(topBar()).findByText('dev-minotaur')).toBeInTheDocument()
    expect(fetch).toHaveBeenCalledWith('/api/nas', expect.anything())
  })

  it('leaves the host out when the collector has no data yet', async () => {
    stubNas({ detail: 'no nas data collected yet' }, false)
    renderRoute('/more')

    await waitFor(() => expect(fetch).toHaveBeenCalled())
    expect(within(topBar()).getByText('Home hub')).toBeInTheDocument()
    expect(screen.queryByText('dev-minotaur')).not.toBeInTheDocument()
  })

  it('keeps the navigation when a page crashes', async () => {
    vi.spyOn(console, 'error').mockImplementation(() => {})
    // A malformed payload: /api/services without groups.
    stubNas({ host: 'dev-minotaur' })
    renderRoute('/house/services')

    expect(await screen.findByRole('heading', { level: 1, name: 'Something went wrong' })).toBeInTheDocument()
    expect(within(spaces()).getByRole('link', { name: 'House' })).toBeInTheDocument()
  })

  it('puts a dot on the space and the tab of a page with an open incident, red for an error', async () => {
    stubApi({
      '/api/alerts/incidents': [
        { key: 'a', rule: 'outside_services', severity: 'warning', title: 'TransIP', body: '', opened_at: '2026-11-20T09:00:00Z', last_seen_at: '', resolved_at: null },
        { key: 'b', rule: 'backup_missing', severity: 'error', title: 'Dump', body: '', opened_at: '2026-11-20T09:00:00Z', last_seen_at: '', resolved_at: null },
      ],
    })
    renderRoute('/more')

    const house = within(spaces()).getByRole('link', { name: /^House/ })
    expect(await within(house).findByText(', has an error')).toBeInTheDocument()
    expect(house.querySelector('[data-look]')).toHaveAttribute('data-look', 'down')
    expect(within(spaces()).getByRole('link', { name: 'Now' }).querySelector('[data-look]')).toBeNull()
    expect(within(tabBar()).getByRole('link', { name: /^House/ }).querySelector('[data-look="down"]')).not.toBeNull()
  })

  it('marks the tabs that need a look, not the overview', async () => {
    stubApi({
      '/api/alerts/incidents': [
        { key: 'a', rule: 'outside_services', severity: 'warning', title: 'TransIP', body: '', opened_at: '2026-11-20T09:00:00Z', last_seen_at: '', resolved_at: null },
      ],
    })
    renderRoute('/house/repos')

    const tabs = screen.getByRole('navigation', { name: 'House pages' })
    expect(await within(tabs).findByRole('link', { name: 'Services, needs a look' })).toBeInTheDocument()
    expect(within(tabs).getByRole('link', { name: 'Overview' }).querySelector('[data-look]')).toBeNull()
    expect(within(tabs).getByRole('link', { name: 'Docker' }).querySelector('[data-look]')).toBeNull()
  })
})
