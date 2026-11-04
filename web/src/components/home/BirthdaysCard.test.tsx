import { render, screen, within } from '@testing-library/react'
import type { Birthdays } from '../../lib/types'
import { BirthdaysCard } from './BirthdaysCard'

const data = (birthdays: Birthdays['birthdays'], stale = false): Birthdays => ({
  as_of: new Date(2026, 10, 4, 9, 0).toISOString(), stale, today: '2026-11-04', birthdays,
})

describe('BirthdaysCard', () => {
  it('lists the week ahead with when and the age they turn', () => {
    render(<BirthdaysCard data={data([
      { name: 'Anna de Vries', date: '2026-11-04', days: 0, turns: 34 },
      { name: 'Bram van Dijk', date: '2026-11-05', days: 1, turns: null },
      { name: 'Cas', date: '2026-11-10', days: 6, turns: 26 },
    ])} />)

    const [anna, bram, cas] = within(screen.getByRole('region', { name: 'Birthdays' })).getAllByRole('listitem')
    expect(anna).toHaveTextContent('Wed4Anna de Vriesturns 34Today')
    expect(bram).toHaveTextContent('Bram van DijkTomorrow')
    expect(bram).not.toHaveTextContent('turns')
    expect(cas).toHaveTextContent('Tue10Casturns 26in 6 days')
  })

  it('stays on Home with nobody this week, and says when it is old or missing', () => {
    const { unmount } = render(<BirthdaysCard data={data([], true)} />)
    expect(screen.getByText('No birthdays this week.')).toBeInTheDocument()
    expect(screen.getByRole('status')).toHaveTextContent('last known')
    unmount()

    const { unmount: again } = render(<BirthdaysCard data={undefined} />)
    expect(screen.getByRole('status')).toHaveTextContent('Loading birthdays')
    again()

    render(<BirthdaysCard data={undefined} error={new Error('503')} />)
    expect(screen.getByText(/Birthdays are not available right now/)).toBeInTheDocument()
  })
})
