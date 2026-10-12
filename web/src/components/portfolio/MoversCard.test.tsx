import { render, screen, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import type { HoldingRow } from '../../lib/portfolioTypes'
import { MoversCard } from './MoversCard'

const row = (symbol: string, weight_pct: number, day_pct: number): HoldingRow => ({
  symbol, name: `${symbol} Inc`, value: weight_pct * 100, day_pct, weight_pct, data_source: 'YAHOO', isin: null,
  currency: 'EUR', quantity: 1, price: 1, day_abs: 0, invested: null, gain_abs: null, gain_pct: null,
})

const HOLDINGS = [row('VWRL', 43, 0.41), row('NVDA', 30, 2.84), row('ASML', 21, -1.12), row('BESI', 2, 3.9), row('ASRNL', 1.5, -0.21), row('TINY', 1, 0)]

function setup(holdings = HOLDINGS) {
  render(
    <MemoryRouter>
      <MoversCard holdings={holdings} />
    </MemoryRouter>,
  )
  return screen.getByRole('region', { name: "Today's movers" })
}

describe('MoversCard', () => {
  it('counts up and down, and gives every holding a tile that opens it', () => {
    const card = setup()
    expect(card).toHaveTextContent('4 up · 2 down')

    // The wide map holds every holding, biggest first.
    const wide = card.querySelector('.md\\:block')!
    const links = within(wide as HTMLElement).getAllByRole('link')
    expect(links.map((l) => l.getAttribute('aria-label'))).toEqual([
      'VWRL, up 0,41% today', 'NVDA, up 2,84% today', 'ASML, down 1,12% today',
      'BESI, up 3,90% today', 'ASRNL, down 0,21% today', 'TINY, up 0,00% today',
    ])
    expect(links[1]).toHaveAttribute('href', '/portfolio?h=YAHOO%2FNVDA')
    // Green up, red down, stronger for a bigger move.
    expect(links[1].style.background).toContain('63, 185, 127')
    expect(links[2].style.background).toContain('229, 100, 106')
  })

  it('merges holdings under 3% into one tile on a phone', () => {
    const card = setup()
    const phone = card.querySelector('.md\\:hidden') as HTMLElement
    const links = within(phone).getAllByRole('link')
    expect(links.map((l) => l.getAttribute('aria-label')?.split(',')[0])).toEqual(['VWRL', 'NVDA', 'ASML', '3 smaller holdings'])
    const others = within(phone).getByRole('link', { name: /3 smaller holdings/ })
    expect(others).toHaveAttribute('href', '#holdings')
    // Their move together, weighted by size: (2 × 3,9 − 1,5 × 0,21 + 0) / 4,5.
    expect(others).toHaveAccessibleName('3 smaller holdings, together up 1,66% today')
  })

  it('keeps one small holding as its own tile, and shows nothing without weights', () => {
    const card = setup(HOLDINGS.slice(0, 4))
    const phone = card.querySelector('.md\\:hidden') as HTMLElement
    expect(within(phone).getAllByRole('link')).toHaveLength(4)

    const { container } = render(
      <MemoryRouter>
        <MoversCard holdings={[row('X', 0, 1)]} />
      </MemoryRouter>,
    )
    expect(container).toBeEmptyDOMElement()
  })
})
