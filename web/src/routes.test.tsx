import { screen, waitFor, within } from '@testing-library/react'
import { NAV_ITEMS } from './lib/navigation'
import { BUILT_ROUTES } from './routes'
import { renderRoute } from './test/renderRoute'

const PLACEHOLDERS = NAV_ITEMS.filter((item) => !BUILT_ROUTES.includes(item.to))

describe('routes', () => {
  it.each(PLACEHOLDERS.map((item) => [item.to, item]))('%s shows its placeholder', (path, item) => {
    renderRoute(path)

    expect(screen.getByRole('heading', { level: 1, name: item.label })).toBeInTheDocument()
    expect(screen.getByText(item.description)).toBeInTheDocument()
    expect(screen.getByText(new RegExp(`milestone ${item.milestone}\\b`))).toBeInTheDocument()
    expect(document.title).toBe(`${item.label} · Home hub`)
  })

  it('renders built sections instead of their placeholder', () => {
    renderRoute('/house/services')

    expect(screen.getByRole('heading', { level: 1, name: 'Services' })).toBeInTheDocument()
    expect(screen.queryByText(/arrives with milestone/)).not.toBeInTheDocument()
  })

  it('lists the spaces without a tab, Ask and Settings on the More page', () => {
    renderRoute('/more')

    const main = within(screen.getByRole('main'))
    expect(main.getByRole('heading', { level: 1, name: 'More' })).toBeInTheDocument()
    expect(main.getAllByRole('link').map((link) => link.querySelector('span span')?.textContent)).toEqual([
      'Portfolio',
      'Recipes',
      'Ask',
      'Settings',
    ])
    expect(main.getByText('This computer')).toBeInTheDocument()
  })

  it.each([
    ['/nas', '/house/nas'],
    ['/tailscale', '/house/network'],
    ['/alerts/7', '/house/alerts/7'],
    ['/recipes/kip-shoarma/cook?persons=3', '/kitchen/recipes/kip-shoarma/cook?persons=3'],
    ['/portfolio?import', '/money/portfolio?import'],
    ['/news?a=a1#top', '/read/news?a=a1#top'],
    ['/house', '/house/nas'],
    ['/now', '/'],
    ['/money', '/money/portfolio'],
  ])('moves the old address %s to %s', async (from, to) => {
    const { router } = renderRoute(from)

    await waitFor(() => {
      const { pathname, search, hash } = router.state.location
      expect(pathname + search + hash).toBe(to)
    })
  })

  it('shows a not-found page for unknown addresses', () => {
    renderRoute('/does-not-exist')

    expect(screen.getByRole('heading', { level: 1, name: 'Page not found' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Back to Home' })).toHaveAttribute('href', '/')
  })
})
