import { fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { overview } from '../../test/runningFixtures'
import { StreetsCard } from './StreetsCard'

describe('StreetsCard', () => {
  it("shows the year's streets, with a new picture for every run", () => {
    render(<StreetsCard data={overview({ streets_at: '2026-10-26T15:00:00Z' })} />, { wrapper: MemoryRouter })

    const card = screen.getByRole('region', { name: `Your streets, ${new Date().getFullYear()}` })
    expect(card).toHaveTextContent('138 runs · 1.214 km')
    expect(screen.getByRole('img').getAttribute('src')).toContain('138-r1-2026-10-26')
    expect(screen.queryByRole('link', { name: /Settings/ })).not.toBeInTheDocument()
  })

  it('says where to fetch the streets before they are in, and goes when the picture fails', () => {
    render(<StreetsCard data={overview({ streets_at: null })} />, { wrapper: MemoryRouter })

    expect(screen.getByRole('link', { name: 'Settings → Running' })).toHaveAttribute('href', '/settings/running')
    fireEvent.error(screen.getByRole('img'))
    expect(screen.queryByRole('region')).not.toBeInTheDocument()
  })

  it('shows nothing before the first run of the year', () => {
    const none = overview()
    const { container } = render(<StreetsCard data={{ ...none, totals: { ...none.totals, runs_this_year: 0 } }} />, { wrapper: MemoryRouter })
    expect(container).toBeEmptyDOMElement()
  })
})
