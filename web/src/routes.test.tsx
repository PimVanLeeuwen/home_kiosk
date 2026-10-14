import { screen, within } from '@testing-library/react'
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
    renderRoute('/services')

    expect(screen.getByRole('heading', { level: 1, name: 'Services' })).toBeInTheDocument()
    expect(screen.queryByText(/arrives with milestone/)).not.toBeInTheDocument()
  })

  it('lists the sections without a tab on the More page', () => {
    renderRoute('/more')

    const main = within(screen.getByRole('main'))
    expect(main.getByRole('heading', { level: 1, name: 'More' })).toBeInTheDocument()
    expect(main.getAllByRole('link').map((link) => link.querySelector('span span')?.textContent)).toEqual([
      'Lights',
      'Saved',
      'Docker',
      'Backups',
      'Services',
      'Media',
      'Tailscale',
      'Repos',
      'Alerts',
      'Settings',
    ])
  })

  it('shows a not-found page for unknown addresses', () => {
    renderRoute('/does-not-exist')

    expect(screen.getByRole('heading', { level: 1, name: 'Page not found' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Back to Home' })).toHaveAttribute('href', '/')
  })
})
