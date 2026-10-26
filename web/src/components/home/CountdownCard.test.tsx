import { render, screen } from '@testing-library/react'
import type { Countdowns } from '../../lib/pieceTypes'
import { tunnel } from '../../lib/countdown'
import { CountdownCard } from './CountdownCard'

const NOW = new Date(2026, 9, 26, 9, 0)
const data = (dates: string[], stale = false): Countdowns => ({
  as_of: NOW.toISOString(), stale,
  events: dates.map((date, i) => ({ title: ['Lisbon', "Anna's birthday"][i], date, colour: '#e6965a', calendar: 'Home' })),
})

describe('CountdownCard', () => {
  it('counts the days to the nearest countdown, with the next one below', () => {
    render(<CountdownCard data={data(['2026-11-14', '2027-03-03'])} now={NOW} />)

    const card = screen.getByRole('region', { name: 'Countdown' })
    expect(card).toHaveTextContent('Sat 14 Nov')
    expect(card).toHaveTextContent('19')
    expect(screen.getByText('days to')).toBeInTheDocument()
    expect(screen.getByText('Lisbon')).toBeInTheDocument()
    expect(screen.getByText("Then Anna's birthday in 128 days")).toBeInTheDocument()
  })

  it('says Today on the day itself and leaves out what has passed', () => {
    render(<CountdownCard data={data(['2026-10-25', '2026-10-26'], true)} now={NOW} />)

    expect(screen.getByText('Today')).toBeInTheDocument()
    expect(screen.getByText("Anna's birthday")).toBeInTheDocument()
    expect(screen.queryByText('days to')).not.toBeInTheDocument()
    expect(screen.getByRole('status')).toHaveTextContent('last known')
  })

  it('shows nothing without a countdown ahead', () => {
    const { container } = render(<CountdownCard data={data(['2026-10-01'])} now={NOW} />)
    expect(container).toBeEmptyDOMElement()
  })

  it('draws one ring per day, at most forty, the far ones white-hot', () => {
    expect(tunnel(19)).toHaveLength(19)
    expect(tunnel(400)).toHaveLength(40)
    expect(tunnel(0)).toHaveLength(1)
    const rings = tunnel(19)
    expect(rings[0].white).toBeGreaterThan(rings[rings.length - 1].white)
    expect(rings[0].rx).toBeLessThan(rings[rings.length - 1].rx)
  })
})
