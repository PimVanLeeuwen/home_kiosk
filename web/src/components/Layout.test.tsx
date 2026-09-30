import { screen, waitFor, within } from '@testing-library/react'
import { vi } from 'vitest'
import { renderRoute } from '../test/renderRoute'

function stubNas(body: unknown, ok = true) {
  vi.stubGlobal(
    'fetch',
    vi.fn(() => Promise.resolve(new Response(JSON.stringify(body), { status: ok ? 200 : 503 }))),
  )
}

const sidebar = () => screen.getAllByRole('navigation', { name: 'Sections' })[0]
const tabBar = () => screen.getAllByRole('navigation', { name: 'Sections' })[1]

describe('Layout', () => {
  it('groups the sidebar into sections with headings', () => {
    renderRoute('/')

    const nav = within(sidebar())
    for (const heading of ['Read', 'Money', 'House', 'System']) {
      expect(nav.getByText(heading)).toBeInTheDocument()
    }
    expect(nav.getAllByRole('link')).toHaveLength(10)
  })

  it('marks the current section in the sidebar', () => {
    renderRoute('/backups')

    expect(within(sidebar()).getByRole('link', { name: 'Backups' })).toHaveAttribute(
      'aria-current',
      'page',
    )
    expect(within(sidebar()).getByRole('link', { name: 'Home' })).not.toHaveAttribute(
      'aria-current',
    )
  })

  it('shows four tabs plus More on mobile', () => {
    renderRoute('/')

    const names = within(tabBar())
      .getAllByRole('link')
      .map((link) => link.textContent)
    expect(names).toEqual(['Home', 'News', 'Portfolio', 'NAS', 'More'])
  })

  it('highlights More while on a section that lives under it', () => {
    renderRoute('/alerts')

    expect(within(tabBar()).getByRole('link', { name: 'More' })).toHaveAttribute(
      'aria-current',
      'page',
    )
    expect(within(tabBar()).getByRole('link', { name: 'Home' })).not.toHaveAttribute(
      'aria-current',
    )
  })

  it('shows the NAS host name under the brand once the collector answers', async () => {
    stubNas({ host: 'dev-minotaur' })
    // A page without data of its own, so only the layout reads /api/nas.
    renderRoute('/more')

    expect(await within(sidebar().parentElement!).findByText('dev-minotaur')).toBeInTheDocument()
    expect(fetch).toHaveBeenCalledWith('/api/nas', expect.anything())
  })

  it('leaves the host out when the collector has no data yet', async () => {
    stubNas({ detail: 'no nas data collected yet' }, false)
    renderRoute('/more')

    await waitFor(() => expect(fetch).toHaveBeenCalled())
    expect(screen.getAllByText('Home hub')).toHaveLength(2) // sidebar and mobile header
    expect(screen.queryByText('dev-minotaur')).not.toBeInTheDocument()
  })

  it('keeps the navigation when a page crashes', async () => {
    vi.spyOn(console, 'error').mockImplementation(() => {})
    // A malformed payload: /api/services without groups.
    stubNas({ host: 'dev-minotaur' })
    renderRoute('/services')

    expect(await screen.findByRole('heading', { level: 1, name: 'Something went wrong' })).toBeInTheDocument()
    expect(within(sidebar()).getByRole('link', { name: 'Home' })).toBeInTheDocument()
  })

  it('shows how the hub was reached', () => {
    renderRoute('/')

    // jsdom serves the page from localhost.
    expect(screen.getAllByText('This computer').length).toBeGreaterThan(0)
  })
})
